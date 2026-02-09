from django.contrib import admin
from .models import Expense

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'amount', 'date', 'created_by', 'is_deleted']
    list_filter = ['category', 'payment_method', 'date', 'is_deleted']
    search_fields = ['name', 'description', 'recipient']
    readonly_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'category', 'amount', 'description')
        }),
        ('Payment Details', {
            'fields': ('payment_method', 'reference_number', 'recipient', 'date')
        }),
        ('Audit Trail', {
            'fields': ('created_by', 'updated_by', 'created_at', 'updated_at', 'is_deleted', 'deleted_at'),
            'classes': ('collapse',)
        }),
    )