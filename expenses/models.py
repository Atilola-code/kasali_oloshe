from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator

class Expense(models.Model):
    CATEGORY_CHOICES = [
        ('salary', 'Salary Payment'),
        ('rent', 'Rent'),
        ('utilities', 'Utilities'),
        ('supplies', 'Office Supplies'),
        ('maintenance', 'Maintenance'),
        ('transport', 'Transport'),
        ('marketing', 'Marketing'),
        ('other', 'Other'),
    ]
    
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )
    description = models.TextField(blank=True, null=True)
    reference_number = models.CharField(max_length=100, blank=True, null=True)
    recipient = models.CharField(max_length=200, blank=True, null=True)
    payment_method = models.CharField(
        max_length=20,
        choices=[
            ('cash', 'Cash'),
            ('bank', 'Bank Transfer'),
            ('cheque', 'Cheque'),
        ],
        default='bank'
    )
    date = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_expenses'
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_expenses'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-date']
        indexes = [
            models.Index(fields=['-date']),
            models.Index(fields=['category']),
            models.Index(fields=['created_by']),
        ]
    
    def __str__(self):
        return f"{self.name} - ₦{self.amount} ({self.get_category_display()})"
    
    def soft_delete(self, user):
        """Soft delete expense"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.updated_by = user
        self.save(update_fields=['is_deleted', 'deleted_at', 'updated_by', 'updated_at'])