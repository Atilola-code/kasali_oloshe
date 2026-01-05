from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from .models import Product, StockAudit


@receiver(pre_save, sender=Product)
def store_old_quantity(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_instance = Product.objects.get(pk=instance.pk)
            instance._old_quantity = old_instance.quantity
        except Product.DoesNotExist:
            instance._old_quantity = None
    else:
        instance._old_quantity = None

@receiver(post_save, sender=Product)
def check_low_stock(sender, instance, created, **kwargs):
    if instance.quantity <= instance.low_stock_threshold:
        subject = f"Low Stock Alert for: {instance.name}"
        message = (
            f"Product '{instance.name}' is low in stock.\n"
            f"Remaining quantity: {instance.quantity}\n"
            f"Threshold: {instance.low_stock_threshold}"
        )
        send_mail(
            subject,
            message,
            "noreply@inventoryapp.com",
            ["hammedolasupo03@gmail.com"],
            fail_silently=True,
        )


@receiver(post_save, sender=Product)
def log_stock_change(sender, instance, created, **kwargs):

    # Log only to StockAudit table if quantity has changed and it's not a new product

    if created:
        return
    
    # Only log if old quantity exists and is different from new quantity
    if hasattr(instance, "_old_quantity") and instance._old_quantity is not None:
        if instance.pk and instance._old_quantity != instance.quantity:
            StockAudit.objects.create(
                product=instance,
                old_quantity=instance._old_quantity,
                new_quantity=instance.quantity,
                changed_by=getattr(instance, "_updated_by", None),
                reason=getattr(instance, "_update_reason", "Sale or manual update")
            )


