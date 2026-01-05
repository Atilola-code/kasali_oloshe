# sales/models.py
from django.db import models
import uuid
from django.utils import timezone
from inventory.models import Product
from django.conf import settings
from user.models import User

class Sale(models.Model):
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('transfer', 'Transfer'),
        ('pos', 'POS'),
        ('credit', 'Credit'),
    ]

    invoice_id = models.CharField(max_length=20, unique=True, editable=False)
    cashier = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    customer_name = models.CharField(max_length=100, blank=True, null=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)    # sum of line subtotals
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    vat_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    change_due = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    date = models.DateTimeField(default=timezone.now)
    receipt_print_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Invoice {self.invoice_id} - {self.total_amount}"
    
    def save(self, *args, **kwargs):
        if not self.invoice_id:
            # Auto-generate unique invoice ID
            self.invoice_id = f"INV-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def increment_print_count(self):
        """Increment the print count by 1"""
        self.receipt_print_count += 1
        self.save(update_fields=['receipt_print_count'])
        
class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, editable=False)

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"

    def save(self, *args, **kwargs):
        self.subtotal = self.quantity * self.unit_price
        super().save(*args, **kwargs)

class Deposit(models.Model):
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    depositor_name = models.CharField(max_length=100)
    bank_name = models.CharField(max_length=100)
    date = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Deposit #{self.id} - {self.amount} - {self.bank_name}"

class StopSaleLog(models.Model):
    is_stopped = models.BooleanField(default=False)
    stopped_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='stopped_sales')
    stopped_at = models.DateTimeField(null=True, blank=True)
    resumed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resumed_sales')
    resumed_at = models.DateTimeField(null=True, blank=True)
    reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Sales {'Stopped' if self.is_stopped else 'Active'} at {self.stopped_at}"
    

class Credit(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('partially_paid', 'Partially Paid'),
        ('cleared', 'Cleared'),
    ]
    
    sale = models.OneToOneField(Sale, on_delete=models.CASCADE, related_name='credit')
    invoice_id = models.CharField(max_length=20)
    customer_name = models.CharField(max_length=100)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    outstanding_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    date = models.DateTimeField()
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_credits')

    def __str__(self):
        return f"Credit {self.invoice_id} - {self.customer_name}"
    
    def update_status(self):
        """Update credit status based on payments"""
        if self.outstanding_amount <= 0:
            self.status = 'cleared'
        elif self.amount_paid > 0:
            self.status = 'partially_paid'
        else:
            self.status = 'pending'
        self.save(update_fields=['status'])


class CreditPayment(models.Model):
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('transfer', 'Transfer'),
        ('pos', 'POS'),
        ('bank', 'Bank Deposit'),
    ]
    
    credit = models.ForeignKey(Credit, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    customer_name = models.CharField(max_length=100)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    remarks = models.TextField(blank=True, null=True)
    date = models.DateTimeField(auto_now_add=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    def __str__(self):
        return f"Payment {self.id} - {self.amount} for {self.credit.invoice_id}"
    
    def save(self, *args, **kwargs):
        # Update credit when payment is made
        if not self.pk:  # New payment
            self.credit.amount_paid += self.amount
            self.credit.outstanding_amount -= self.amount
            self.credit.save(update_fields=['amount_paid', 'outstanding_amount'])
            self.credit.update_status()
        super().save(*args, **kwargs)