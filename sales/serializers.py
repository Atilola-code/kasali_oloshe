# sales/serializers.py
from rest_framework import serializers
from django.db import transaction
from .models import Sale, SaleItem,Deposit, StopSaleLog, Credit, CreditPayment
from inventory.models import Product
import uuid
from user.serializers import UserSerializer

class SaleItemSerializer(serializers.ModelSerializer):
    product = serializers.CharField()
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_id = serializers.IntegerField(source='product.id', read_only=True)

    class Meta:
        model = SaleItem
        fields = ['id', 'product', 'product_name', 'product_id', 'quantity', 'unit_price', 'subtotal']
        read_only_fields = ['id', 'subtotal', 'product_name', 'product_id']

    def validate_product(self, value):
        # Accept either product name or SKU
        product = Product.objects.filter(name__iexact=value).first()
        # If not found by name, try SKU
        if not product:
            product = Product.objects.filter(sku__iexact=value).first()

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
    # optional input fields for convenience:
    discount_percent = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, write_only=True)
    vat_percent = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, write_only=True)

    class Meta:
        model = Sale
        fields = ['id', 'invoice_id', 'cashier', 'cashier_name', 'customer_name', 'date', 'subtotal','discount_amount','vat_amount', 'total_amount', 'payment_method', 'amount_paid', 'change_due', 'items', 'discount_percent','vat_percent', 'receipt_print_count']
        read_only_fields = ['id', 'invoice_id','subtotal','total_amount','change_due', 'date', 'cashier']

    def validate(self, attrs):
        items = attrs.get('items', [])
        if not items:
            raise serializers.ValidationError({"items": "A sale must include at least one item."})
        
        # Logging for debugging
        print(f"DEBUG: Validating {len(items)} items")

        # ensure stock available
        for i, item in enumerate(items):
            product = item['product']
            print(f"DEBUG: Item {i} - Product: {product.name}, Quantity: {item['quantity']}, Available: {product.quantity}")
            
            if product.quantity < item['quantity']:
                raise serializers.ValidationError(
                    {"error": f"Insufficient stock for {product.name}. Available quantity: {product.quantity}"}
                    )
        return attrs
    
    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        discount_percent = validated_data.pop('discount_percent', 0) or 0
        vat_percent = validated_data.pop('vat_percent', 0) or 0
        user = self.context['request'].user

        # calculate subtotal from items
        subtotal = sum(
            item_data['quantity'] * item_data['unit_price']
            for item_data in items_data
        )

        discount_amount = round((subtotal * (discount_percent / 100)), 2) if discount_percent else 0
        vat_base = subtotal - discount_amount
        vat_amount = round((vat_base * (vat_percent / 100)), 2) if vat_percent else 0
        total = round(vat_base + vat_amount, 2)

        # Calculate change
        amount_paid = validated_data.get('amount_paid', 0)
        change_due = round(amount_paid - total, 2) if amount_paid >= total else 0
        
        # Generate invoice ID if not provided
        invoice_id = validated_data.get('invoice_id') or f"INV-{uuid.uuid4().hex[:8].upper()}"


        # Create the sale
        sale = Sale.objects.create(
            invoice_id=invoice_id,
            cashier=user,
            customer_name=validated_data.get('customer_name', ''),
            subtotal=subtotal,
            discount_amount=discount_amount,
            vat_amount=vat_amount,
            total_amount=total,
            payment_method=validated_data.get('payment_method', 'cash'),
            amount_paid=amount_paid,
            change_due=change_due
        )

        for item_data in items_data:
            product = item_data['product']

            # Lock the product row for update
            product = Product.objects.select_for_update().get(pk=product.id)
            
            # Double-check stock (race condition protection)
            if product.quantity < item_data['quantity']:
                raise serializers.ValidationError(f"Not enough stock for {product.name}. Avalailable quantity: {product.quantity}")

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
        
        # Update simple fields
        for attr, value in validated_data.items():
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
            
            # Create new items (similar to create logic)
            discount_percent = validated_data.pop('discount_percent', 0) or 0
            vat_percent = validated_data.pop('vat_percent', 0) or 0
            
            # Recalculate subtotal from new items
            subtotal = sum(
                item_data['quantity'] * item_data['unit_price']
                for item_data in items_data
            )
            
            discount_amount = round((subtotal * (discount_percent / 100)), 2) if discount_percent else 0
            vat_base = subtotal - discount_amount
            vat_amount = round((vat_base * (vat_percent / 100)), 2) if vat_percent else 0
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