# sales/signals.py
from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver
from django.core.cache import cache
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from .models import Sale, Credit


@receiver(post_migrate)
def initialize_stop_sale_cache(sender, **kwargs):
    """Initialize stop sale cache after migrations"""
    if cache.get('is_sale_stopped') is None:
        cache.set('is_sale_stopped', False, timeout=None)
        print("✓ Stop sale cache initialized to False")


@receiver(post_save, sender=Sale)
def create_credit_for_credit_sale(sender, instance, created, **kwargs):
    """Automatically create a Credit record for credit sales"""
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


@receiver(post_save, sender=Sale)
def send_sales_receipt(sender, instance, created, **kwargs):
    """Send sales receipt email to customer (if email provided) and admin"""
    
    if not created:
        return  # Only send on new sales
    
    subject = f"Receipt for Invoice {instance.invoice_id}"
    
    # Prepare items data
    items = []
    for item in instance.items.all():
        items.append({
            'product_name': item.product.name if item.product else 'N/A',
            'quantity': item.quantity,
            'unit_price': f"{item.unit_price:,.2f}",
            'subtotal': f"{item.subtotal:,.2f}",
        })
    
    # Calculate VAT percentage if applicable
    vat_percent = 0
    if instance.vat_amount > 0 and instance.subtotal > 0:
        vat_percent = (instance.vat_amount / (instance.subtotal - instance.discount_amount)) * 100
    
    # Prepare context
    context = {
        'invoice_id': instance.invoice_id,
        'date': instance.date.strftime('%B %d, %Y %I:%M %p'),
        'customer_name': instance.customer_name or 'Walk-in Customer',
        'cashier_name': instance.cashier.get_full_name() if instance.cashier else 'System',
        'payment_method': instance.get_payment_method_display(),
        'items': items,
        'subtotal': f"{instance.subtotal:,.2f}",
        'discount_amount': f"{instance.discount_amount:,.2f}",
        'vat_amount': f"{instance.vat_amount:,.2f}",
        'vat_percent': f"{vat_percent:.1f}" if vat_percent > 0 else 0,
        'total_amount': f"{instance.total_amount:,.2f}",
        'amount_paid': f"{instance.amount_paid:,.2f}",
        'change_due': f"{instance.change_due:,.2f}",
        'outstanding_amount': f"{instance.total_amount - instance.amount_paid:,.2f}" if instance.payment_method == 'credit' else "0.00",
        'contact_email': settings.EMAIL_HOST_USER,
    }
    
    # Render HTML email
    html_content = render_to_string('emails/sales_receipt.html', context)
    
    # Create plain text version
    text_content = f"""
Sales Receipt

Invoice: {instance.invoice_id}
Date: {instance.date.strftime('%B %d, %Y %I:%M %p')}
Customer: {instance.customer_name or 'Walk-in Customer'}
Payment Method: {instance.get_payment_method_display()}

Items:
"""
    for item in items:
        text_content += f"\n- {item['product_name']}: {item['quantity']} x ₦{item['unit_price']}"
    
    text_content += f"""

Subtotal: ₦{instance.subtotal:,.2f}
Discount: ₦{instance.discount_amount:,.2f}
VAT: ₦{instance.vat_amount:,.2f}
Total: ₦{instance.total_amount:,.2f}
Amount Paid: ₦{instance.amount_paid:,.2f}
Change: ₦{instance.change_due:,.2f}

Thank you for your purchase!

Kasali Oloshe Inventory Management
Contact: {settings.EMAIL_HOST_USER}
    """
    
    # Send to admin/store email
    recipients = [settings.EMAIL_HOST_USER]
    
    # Send email
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=recipients,
    )
    email.attach_alternative(html_content, "text/html")
    
    try:
        email.send(fail_silently=False)
        print(f"✓ Sales receipt email sent for {instance.invoice_id}")
    except Exception as e:
        print(f"✗ Failed to send sales receipt: {str(e)}")