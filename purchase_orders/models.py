from django.db import models

# Create your models here.
# purchase_orders/models.py
from django.db import models
from django.utils import timezone
from inventory.models import Product
from user.models import User
import uuid

class PurchaseOrder(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('received', 'Received'),
        ('cancelled', 'Cancelled'),
    ]
    
    po_number = models.CharField(max_length=20, unique=True, editable=False)
    supplier_name = models.CharField(max_length=200)
    order_date = models.DateTimeField(default=timezone.now)
    expected_delivery = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    stock_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_pos')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_pos')
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_pos')
    approved_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.po_number} - {self.supplier_name}"
    
    def save(self, *args, **kwargs):
        if not self.po_number:
            # Generate PO number: PO-YYYYMMDD-XXXX
            date_str = timezone.now().strftime('%Y%m%d')
            random_str = uuid.uuid4().hex[:4].upper()
            self.po_number = f"PO-{date_str}-{random_str}"
        super().save(*args, **kwargs)
    
    def calculate_totals(self):
        """Calculate total amount and stock value from items"""
        items = self.items.all()
        self.total_amount = sum(item.subtotal for item in items)
        self.stock_value = sum(item.stock_value for item in items)
        self.save(update_fields=['total_amount', 'stock_value'])


class PurchaseOrderItem(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    product_name = models.CharField(max_length=200)  # Store name in case product is deleted
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    stock_value = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    
    def __str__(self):
        return f"{self.product_name} x {self.quantity}"
    
    def save(self, *args, **kwargs):
        self.subtotal = self.quantity * self.unit_price
        self.stock_value = self.quantity * (self.product.cost_price if self.product else 0)
        if not self.product_name:
            self.product_name = self.product.name
        super().save(*args, **kwargs)


class PurchaseOrderHistory(models.Model):
    """Track status changes and actions on PO"""
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='history')
    action = models.CharField(max_length=100)
    old_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20, blank=True)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.purchase_order.po_number} - {self.action} at {self.timestamp}"