# sales/serializers.py
from rest_framework import serializers
from django.db import transaction
from django.db.models import Q
from .models import Sale, SaleItem,Deposit, StopSaleLog, Credit, CreditPayment
from inventory.models import Product
import uuid
from user.serializers import UserSerializer
from decimal import Decimal

class SaleItemSerializer(serializers.ModelSerializer):
    product = serializers.CharField()
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_id = serializers.IntegerField(source='product.id', read_only=True)

    class Meta:
        model = SaleItem
        fields = ['id', 'product', 'product_name', 'product_id', 'quantity', 'unit_price', 'subtotal']
        read_only_fields = ['id', 'subtotal', 'product_name', 'product_id']

    def validate_product(self, value):
        # Check if value is numeric (could be product ID)
        if str(value).isdigit():
            try:
                product = Product.objects.get(id=int(value))
                return product
            except Product.DoesNotExist:
                raise serializers.ValidationError(f"Product with ID {value} not found")
        
        # Otherwise, treat as product name or SKU
        product = Product.objects.filter(
            Q(name__iexact=value) | Q(sku__iexact=value)
        ).first()
        
        if not product:
            raise serializers.ValidationError(
                f"Product '{value}' not found. Please use exact product name or SKU."
            )
        
        return product

class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True)
    cashier_name = serializers.CharField(source='cashier.get_full_name', read_only=True)
    invoice_id = serializers.CharField(read_only=True)
    date = serializers.DateTimeField(read_only=True)
    # Change from discount_percent to discount_amount
    discount_amount = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False, 
        write_only=True,
        default=0
    )
    vat_percent = serializers.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        required=False, 
        write_only=True,
        default=0
    )

    class Meta:
        model = Sale
        fields = [
            'id', 'invoice_id', 'cashier', 'cashier_name', 'customer_name', 
            'date', 'subtotal', 'discount_amount', 'vat_amount', 'total_amount', 
            'payment_method', 'amount_paid', 'change_due', 'items', 
            'vat_percent', 'receipt_print_count'
        ]
        read_only_fields = [
            'id', 'invoice_id', 'subtotal', 'total_amount', 
            'change_due', 'date', 'cashier', 'vat_amount'
        ]

    def validate(self, attrs):
        items = attrs.get('items', [])
        if not items:
            raise serializers.ValidationError({"items": "A sale must include at least one item."})
        
        # Convert product strings to Product objects and validate stock
        for i, item_data in enumerate(items):
            product_value = item_data.get('product')
            
            if not product_value:
                raise serializers.ValidationError({
                    f"items[{i}].product": "Product is required"
                })
            
            # If product is a string, convert to Product object
            if isinstance(product_value, str):
                try:
                    # Try to find product by name or SKU
                    product = Product.objects.filter(
                        Q(name__iexact=product_value) | Q(sku__iexact=product_value)
                    ).first()
                    
                    if not product:
                        raise serializers.ValidationError({
                            f"items[{i}].product": f"Product '{product_value}' not found"
                        })
                    
                    # Replace string with Product object
                    item_data['product'] = product
                except Exception as e:
                    raise serializers.ValidationError({
                        f"items[{i}].product": f"Error finding product: {str(e)}"
                    })
            
            # Now validate stock
            product = item_data['product']
            quantity = item_data.get('quantity', 0)
            
            if product.quantity < quantity:
                raise serializers.ValidationError({
                    f"items[{i}].quantity": f"Insufficient stock for {product.name}. Available: {product.quantity}"
                })
        
        # Validate discount amount
        discount_amount = attrs.get('discount_amount', 0)
        if discount_amount:
            # Calculate subtotal to validate discount doesn't exceed it
            subtotal = sum(
                item_data['quantity'] * item_data['unit_price']
                for item_data in items
            )
            
            if discount_amount > subtotal:
                raise serializers.ValidationError({
                    'discount_amount': f'Discount amount ({discount_amount}) cannot exceed subtotal ({subtotal})'
                })
        
        return attrs
    
    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        discount_amount = validated_data.pop('discount_amount', 0) or 0
        vat_percent = validated_data.pop('vat_percent', 0) or 0
        user = self.context['request'].user

        # Calculate subtotal from items
        subtotal = sum(
            item_data['quantity'] * item_data['unit_price']
            for item_data in items_data
        )

        # Ensure discount doesn't exceed subtotal
        subtotal_decimal = Decimal(str(subtotal))
        discount_amount_decimal = Decimal(str(discount_amount))
        
        # Ensure discount doesn't exceed subtotal
        discount_amount_decimal = min(discount_amount_decimal, subtotal_decimal)
        
        vat_base = subtotal_decimal - discount_amount_decimal
        vat_amount = round((vat_base * (Decimal(str(vat_percent)) / Decimal('100'))), 2) if vat_percent else Decimal('0')
        total = round(vat_base + vat_amount, 2)

        # Calculate change
        amount_paid = validated_data.get('amount_paid', 0)
        amount_paid_decimal = Decimal(str(amount_paid)) if amount_paid else Decimal('0')
        change_due = round(amount_paid_decimal - total, 2) if amount_paid_decimal >= total else Decimal('0')
            
        # Generate invoice ID
        invoice_id = f"INV-{uuid.uuid4().hex[:8].upper()}"

        # Create the sale
        sale = Sale.objects.create(
            invoice_id=invoice_id,
            cashier=user,
            customer_name=validated_data.get('customer_name', ''),
            subtotal=subtotal_decimal,
            discount_amount=discount_amount_decimal,  # ✅ Store discount amount
            vat_amount=vat_amount,
            total_amount=total,
            payment_method=validated_data.get('payment_method', 'cash'),
            amount_paid=amount_paid_decimal,
            change_due=change_due
        )

        # Create sale items and update stock
        for item_data in items_data:
            product = item_data['product']

            # Lock the product row for update
            product = Product.objects.select_for_update().get(pk=product.id)
            
            # Double-check stock (race condition protection)
            if product.quantity < item_data['quantity']:
                raise serializers.ValidationError(
                    f"Not enough stock for {product.name}. Available quantity: {product.quantity}"
                )

            # Create sale item
            SaleItem.objects.create(
                sale=sale,
                product=product,
                quantity=item_data['quantity'],
                unit_price=item_data['unit_price'],
                subtotal=item_data['quantity'] * item_data['unit_price']
            )
            
            # Update product stock
            product.quantity -= item_data['quantity']
            product.save(update_fields=['quantity'])

        return sale
    
    @transaction.atomic
    def update(self, instance, validated_data):
        # Handle items separately
        items_data = validated_data.pop('items', None)
        discount_amount = validated_data.pop('discount_amount', 0) or 0
        vat_percent = validated_data.pop('vat_percent', 0) or 0
        
        # Update simple fields
        for attr, value in validated_data.items():
            if attr not in ['items', 'discount_amount', 'vat_percent']:
                setattr(instance, attr, value)
        
        # If items are provided, update them
        if items_data is not None:
            # First, restore stock from old items
            old_items = SaleItem.objects.filter(sale=instance)
            for old_item in old_items:
                product = old_item.product
                product.quantity += old_item.quantity
                product.save(update_fields=['quantity'])
            
            # Delete old items
            old_items.delete()
            
            subtotal = sum(
                item_data['quantity'] * item_data['unit_price']
                for item_data in items_data
            )
            
            # ✅ FIXED: Discount is now an amount
            discount_amount = min(Decimal(str(discount_amount)), subtotal)
            vat_base = subtotal - discount_amount
            vat_amount = round((vat_base * (Decimal(str(vat_percent)) / Decimal('100'))), 2) if vat_percent else Decimal('0')
            total = round(vat_base + vat_amount, 2)
            
            # Update sale instance with new totals
            instance.subtotal = subtotal
            instance.discount_amount = discount_amount
            instance.vat_amount = vat_amount
            instance.total_amount = total
            
            # Recalculate change if amount_paid is provided
            if 'amount_paid' in validated_data:
                amount_paid = validated_data.get('amount_paid', 0)
                instance.change_due = round(amount_paid - total, 2) if amount_paid >= total else 0
            
            # Create new sale items
            for item_data in items_data:
                product = item_data['product']
                
                # Lock the product row for update
                product = Product.objects.select_for_update().get(pk=product.id)
                
                # Check stock availability
                if product.quantity < item_data['quantity']:
                    raise serializers.ValidationError(
                        f"Insufficient stock for {product.name}. Available quantity: {product.quantity}"
                    )
                
                # Create sale item
                SaleItem.objects.create(
                    sale=instance,
                    product=product,
                    quantity=item_data['quantity'],
                    unit_price=item_data['unit_price'],
                    subtotal=item_data['quantity'] * item_data['unit_price']
                )
                
                # Update product stock
                product.quantity -= item_data['quantity']
                product.save(update_fields=['quantity'])
        
        instance.save()
        return instance
    
class DepositSerializer(serializers.ModelSerializer):
    class Meta:
        model = Deposit
        fields = ['id', 'amount', 'depositor_name', 'bank_name', 'date', 'created_by', 'created_at']
        read_only_fields = ['created_by', 'created_at']

class StopSaleLogSerializer(serializers.ModelSerializer):
    stopped_by = UserSerializer(read_only=True)
    resumed_by = UserSerializer(read_only=True)
    
    class Meta:
        model = StopSaleLog
        fields = '__all__'
        read_only_fields = ['stopped_by', 'stopped_at', 'resumed_by', 'resumed_at', 'created_at']

class StopSaleStatusSerializer(serializers.Serializer):
    is_sale_stopped = serializers.BooleanField()
    stopped_by = serializers.CharField(allow_null=True)
    stopped_at = serializers.DateTimeField(allow_null=True)
    reason = serializers.CharField(allow_null=True)
    can_resume = serializers.BooleanField(default=False)
    message = serializers.CharField(allow_null=True, required=False)
    resumed_by = serializers.CharField(allow_null=True, required=False)
    resumed_at = serializers.DateTimeField(allow_null=True, required=False)

class CreditPaymentSerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.CharField(source='recorded_by.get_full_name', read_only=True)
    
    class Meta:
        model = CreditPayment
        fields = ['id', 'credit', 'amount', 'customer_name', 'payment_method', 'remarks', 
                  'date', 'recorded_by', 'recorded_by_name']
        read_only_fields = ['id', 'date', 'recorded_by', 'recorded_by_name']


class CreditSerializer(serializers.ModelSerializer):
    payments = CreditPaymentSerializer(many=True, read_only=True)
    
    class Meta:
        model = Credit
        fields = ['id', 'sale', 'invoice_id', 'customer_name', 'total_amount', 
                  'amount_paid', 'outstanding_amount', 'status', 'date', 'payments']
        read_only_fields = ['id', 'invoice_id', 'date']


class ClearCreditSerializer(serializers.Serializer):
    amount_paid = serializers.DecimalField(max_digits=10, decimal_places=2)
    customer_name = serializers.CharField(max_length=100)
    payment_method = serializers.ChoiceField(choices=CreditPayment.PAYMENT_METHODS)
    remarks = serializers.CharField(required=False, allow_blank=True)
    
    def validate_amount_paid(self, value):
        if value <= 0:
            raise serializers.ValidationError("Payment amount must be greater than zero")
        return value