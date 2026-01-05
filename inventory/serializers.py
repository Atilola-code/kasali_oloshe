from rest_framework import serializers
from .models import Product

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'category', 'sku', 'quantity', 'selling_price', 'cost_price', 'low_stock_threshold', 'date_added']
        read_only_fields = ['id', 'date_added']

    def to_representation(self, instance):
        """Hide cost_price for non-admin users"""
        data = super().to_representation(instance)
        request = self.context.get('request')

        if request and request.user.is_authenticated:
            if request.user.role not in ['ADMIN', 'MANAGER']:
                # Hide cost_price for cashiers
                data.pop('cost_price', None)
        return data

class ProductReadOnlySerializer(serializers.ModelSerializer):
    """Serializer for cashiers - read only, no cost_price"""
    class Meta:
        model = Product
        fields = ['id', 'name', 'category', 'sku', 'quantity', 'selling_price', 'low_stock_threshold']
        read_only_fields = fields