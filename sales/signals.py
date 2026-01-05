# sales/signals.py
from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver
from django.core.cache import cache
from .models import Sale, Credit

@receiver(post_migrate)
def initialize_stop_sale_cache(sender, **kwargs):
    """
    Initialize stop sale cache after migrations
    Sets default value to False (sales not stopped)
    """
    if cache.get('is_sale_stopped') is None:
        cache.set('is_sale_stopped', False, timeout=None)
        print("✓ Stop sale cache initialized to False")

@receiver(post_save, sender=Sale)
def create_credit_for_credit_sale(sender, instance, created, **kwargs):
    """
    Automatically create a Credit record when a sale with payment_method='credit' is created
    """
    if created and instance.payment_method == 'credit':
        Credit.objects.create(
            sale=instance,
            invoice_id=instance.invoice_id,
            customer_name=instance.customer_name or 'Walk-in Customer',
            total_amount=instance.total_amount,
            amount_paid=instance.amount_paid,
            outstanding_amount=instance.total_amount - instance.amount_paid,
            date=instance.date,
            created_by=instance.cashier
        )