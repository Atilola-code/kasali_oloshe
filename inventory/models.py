from django.db import models
from django.utils import timezone

class Product(models.Model):
    CATEGORY_CHOICES = [
        ('bath soap', 'Bath Soap'),
        ('liquid detergent', 'Liquid Detergent'),
        ('detergent', 'Detergent'),
        ('others', 'Others'),
    ]

    name = models.CharField(max_length=100)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='bath soap')
    sku = models.CharField(max_length=50, unique=True)
    quantity = models.PositiveIntegerField(default=0)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    low_stock_threshold = models.PositiveIntegerField(default=5)
    date_added = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name

    @property
    def stock_value(self):
        return self.quantity * self.cost_price
    
class StockAudit(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="audits")
    changed_by = models.ForeignKey("user.User", on_delete=models.SET_NULL, null=True, blank=True)
    old_quantity = models.PositiveIntegerField()
    new_quantity = models.PositiveIntegerField()
    change_date = models.DateTimeField(auto_now_add=True)
    reason = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.product.name} changed from {self.old_quantity} to {self.new_quantity}"

