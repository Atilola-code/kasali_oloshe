# purchase_orders/serializers.py
from rest_framework import serializers
from django.db import transaction
from .models import PurchaseOrder, PurchaseOrderItem, PurchaseOrderHistory
from inventory.models import Product

class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(write_only=True)
    product_name = serializers.CharField(read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    
    class Meta:
        model = PurchaseOrderItem
        fields = ['id', 'product_id', 'product_name', 'product_sku', 'quantity', 
                  'unit_price', 'subtotal', 'stock_value']
        read_only_fields = ['id', 'subtotal', 'stock_value', 'product_name']
    
    def validate_product_id(self, value):
        try:
            product = Product.objects.get(id=value)
            return value
        except Product.DoesNotExist:
            raise serializers.ValidationError(f"Product with id {value} does not exist")


class PurchaseOrderHistorySerializer(serializers.ModelSerializer):
    performed_by_name = serializers.CharField(source='performed_by.get_full_name', read_only=True)
    
    class Meta:
        model = PurchaseOrderHistory
        fields = ['id', 'action', 'old_status', 'new_status', 'performed_by_name', 
                  'notes', 'timestamp']


class PurchaseOrderSerializer(serializers.ModelSerializer):
    items = PurchaseOrderItemSerializer(many=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    received_by_name = serializers.CharField(source='received_by.get_full_name', read_only=True)
    history = PurchaseOrderHistorySerializer(many=True, read_only=True)
    
    class Meta:
        model = PurchaseOrder
        fields = ['id', 'po_number', 'supplier_name', 'order_date', 'expected_delivery',
                  'status', 'total_amount', 'stock_value', 'notes', 'created_by', 
                  'created_by_name', 'approved_by', 'approved_by_name', 'received_by',
                  'received_by_name', 'approved_at', 'received_at', 'created_at', 
                  'updated_at', 'items', 'history']
        read_only_fields = ['id', 'po_number', 'total_amount', 'stock_value', 
                            'order_date', 'created_by', 'approved_by', 'received_by',
                            'approved_at', 'received_at', 'created_at', 'updated_at']
    
    def validate(self, data):
        items = data.get('items', [])
        if not items:
            raise serializers.ValidationError({"items": "Purchase order must include at least one item"})
        return data
    
    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        user = self.context['request'].user
        
        # Create PO
        po = PurchaseOrder.objects.create(
            **validated_data,
            created_by=user
        )
        
        # Create PO items
        for item_data in items_data:
            product_id = item_data.pop('product_id')
            product = Product.objects.get(id=product_id)
            
            PurchaseOrderItem.objects.create(
                purchase_order=po,
                product=product,
                product_name=product.name,
                **item_data
            )
        
        # Calculate totals
        po.calculate_totals()
        
        # Log creation
        PurchaseOrderHistory.objects.create(
            purchase_order=po,
            action='Created',
            new_status=po.status,
            performed_by=user,
            notes=f'Purchase order created with {len(items_data)} items'
        )
        
        return po
    
    @transaction.atomic
    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        user = self.context['request'].user
        old_status = instance.status
        
        # Update PO fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update items if provided
        if items_data is not None:
            # Delete old items
            instance.items.all().delete()
            
            # Create new items
            for item_data in items_data:
                product_id = item_data.pop('product_id')
                product = Product.objects.get(id=product_id)
                
                PurchaseOrderItem.objects.create(
                    purchase_order=instance,
                    product=product,
                    product_name=product.name,
                    **item_data
                )
            
            # Recalculate totals
            instance.calculate_totals()
        
        # Log update
        if old_status != instance.status:
            PurchaseOrderHistory.objects.create(
                purchase_order=instance,
                action='Status Changed',
                old_status=old_status,
                new_status=instance.status,
                performed_by=user,
                notes=f'Status changed from {old_status} to {instance.status}'
            )
        
        return instance


class ChangeStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['draft', 'pending', 'approved', 'received', 'cancelled'])
    notes = serializers.CharField(required=False, allow_blank=True)