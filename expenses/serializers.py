from rest_framework import serializers
from .models import Expense

class ExpenseSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.get_full_name', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    
    class Meta:
        model = Expense
        fields = [
            'id', 'name', 'category', 'category_display', 'amount',
            'description', 'reference_number', 'recipient', 'payment_method',
            'date', 'created_by', 'created_by_name', 'updated_by', 'updated_by_name',
            'created_at', 'updated_at', 'is_deleted'
        ]
        read_only_fields = ['id', 'created_by', 'updated_by', 'created_at', 'updated_at']
    
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero")
        return value
    
    def validate(self, data):
        # Validate category
        if data.get('category') not in dict(Expense.CATEGORY_CHOICES):
            raise serializers.ValidationError({
                'category': 'Invalid category selected'
            })
        return data


class ExpenseStatsSerializer(serializers.Serializer):
    total_expenses = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_count = serializers.IntegerField()
    by_category = serializers.DictField()
    by_month = serializers.ListField()
    recent_expenses = ExpenseSerializer(many=True)