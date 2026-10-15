from django.db import models

# purchase_orders/models.py
from django.db import models
from django.utils import timezone
from inventory.models import Product
from user.models import User
import uuid
from decimal import Decimal

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


class CashAtBank(models.Model):
    """
    Ledger-style model to track all cash at bank transactions.
    Positive amounts = money coming in (deposits, digital sales, credit payments)
    Negative amounts = money going out (PO payments, expenses)
    """
    TRANSACTION_TYPES = [
        ('deposit', 'Bank Deposit'),
        ('sale_digital', 'Digital Sale (Transfer/POS)'),
        ('credit_payment', 'Credit Payment'),
        ('purchase_order', 'Purchase Order Payment'),
        ('expense', 'Expense'),
        ('adjustment', 'Manual Adjustment'),
    ]
    
    amount = models.DecimalField(
        max_digits=14, 
        decimal_places=2,
        help_text="Positive = inflow, Negative = outflow"
    )
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    reference = models.CharField(max_length=100, blank=True, help_text="e.g., PO number, Invoice ID")
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='cash_transactions'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Cash at Bank Entry'
        verbose_name_plural = 'Cash at Bank Entries'
    
    def __str__(self):
        direction = '+' if self.amount >= 0 else ''
        return f"{self.get_transaction_type_display()}: {direction}{self.amount} ({self.reference})"
    
    @classmethod
    def get_balance(cls):
        """Calculate current cash at bank balance."""
        from django.db.models import Sum
        result = cls.objects.aggregate(total=Sum('amount'))
        return result['total'] or Decimal('0.00')
    
    @classmethod
    def record_po_payment(cls, po, user):
        """Record a PO payment (deduction) in the ledger."""
        return cls.objects.create(
            amount=-po.total_amount,  # Negative because it's an outflow
            transaction_type='purchase_order',
            reference=po.po_number,
            description=f"Payment for PO {po.po_number} - {po.supplier_name}",
            created_by=user
        )
    
    @classmethod
    def record_deposit(cls, deposit, user):
        """Record a bank deposit (inflow)."""
        return cls.objects.create(
            amount=deposit.amount,
            transaction_type='deposit',
            reference=f"DEP-{deposit.id}",
            description=f"Deposit by {deposit.depositor_name} - {deposit.bank_name}",
            created_by=user
        )
    
    @classmethod
    def record_digital_sale(cls, sale, user):
        """Record a digital sale (transfer/POS) as inflow."""
        if sale.payment_method in ['transfer', 'pos']:
            return cls.objects.create(
                amount=sale.total_amount,
                transaction_type='sale_digital',
                reference=sale.invoice_id,
                description=f"Digital sale ({sale.payment_method}) - {sale.customer_name or 'Walk-in'}",
                created_by=user
            )
        return None
    
    @classmethod
    def record_credit_payment(cls, payment, user):
        """Record a credit payment via transfer/POS/bank as inflow."""
        if payment.payment_method in ['transfer', 'pos', 'bank']:
            return cls.objects.create(
                amount=payment.amount,
                transaction_type='credit_payment',
                reference=payment.credit.invoice_id,
                description=f"Credit payment for {payment.credit.invoice_id} - {payment.customer_name}",
                created_by=user
            )
        return None