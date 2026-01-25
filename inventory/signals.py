# inventory/signals.py
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from .models import Product, StockAudit


@receiver(pre_save, sender=Product)
def store_old_quantity(sender, instance, **kwargs):
    """Store old quantity before save for comparison"""
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
    """Send email alert when stock is low"""
    if instance.quantity <= instance.low_stock_threshold:
        subject = f"⚠️ Low Stock Alert: {instance.name}"
        
        # Prepare context for email template
        context = {
            'product_name': instance.name,
            'sku': instance.sku,
            'category': instance.get_category_display(),
            'quantity': instance.quantity,
            'threshold': instance.low_stock_threshold,
            'stock_value': f"{instance.stock_value:,.2f}",
            'dashboard_url': f"{settings.FRONTEND_URL}/inventory" if hasattr(settings, 'FRONTEND_URL') else '#',
        }
        
        # Render HTML email
        html_content = render_to_string('emails/low_stock_alert.html', context)
        
        # Create plain text version
        text_content = f"""
Low Stock Alert for: {instance.name}

Product: {instance.name}
SKU: {instance.sku}
Category: {instance.get_category_display()}
Current Stock: {instance.quantity} units
Threshold: {instance.low_stock_threshold} units
Stock Value: ₦{instance.stock_value:,.2f}

Recommended Action:
- Create a purchase order immediately
- Contact supplier for restock
- Review sales trends for this product

This is an automated alert from Kasali Oloshe Inventory Management System.
        """
        
        # Send email
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[settings.EMAIL_HOST_USER, 'hammedolasupo03@gmail.com'],
        )
        email.attach_alternative(html_content, "text/html")
        
        try:
            email.send(fail_silently=False)
            print(f"✓ Low stock email sent for {instance.name}")
        except Exception as e:
            print(f"✗ Failed to send low stock email: {str(e)}")


@receiver(post_save, sender=Product)
def log_stock_change(sender, instance, created, **kwargs):
    """Log stock changes to audit table"""
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




