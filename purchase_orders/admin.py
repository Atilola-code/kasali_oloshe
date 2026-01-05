from django.contrib import admin
# Register your models here.

# purchase_orders/admin.py
from django.contrib import admin
from .models import PurchaseOrder, PurchaseOrderItem, PurchaseOrderHistory

class PurchaseOrderItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 1

class PurchaseOrderHistoryInline(admin.TabularInline):
    model = PurchaseOrderHistory
    extra = 0
    readonly_fields = ['action', 'old_status', 'new_status', 'performed_by', 'timestamp']

@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ['po_number', 'supplier_name', 'order_date', 'expected_delivery', 
                    'status', 'total_amount', 'created_by']
    list_filter = ['status', 'order_date', 'expected_delivery']
    search_fields = ['po_number', 'supplier_name']
    inlines = [PurchaseOrderItemInline, PurchaseOrderHistoryInline]
    readonly_fields = ['po_number', 'total_amount', 'stock_value', 'created_at', 'updated_at']