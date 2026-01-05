# purchase_orders/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import PurchaseOrder, PurchaseOrderHistory

@receiver(post_save, sender=PurchaseOrder)
def log_po_status_change(sender, instance, created, **kwargs):
    """Log status changes in purchase order history"""
    if not created:
        # This will be handled in the view's change_status action
        pass