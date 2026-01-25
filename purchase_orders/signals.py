# purchase_orders/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from .models import PurchaseOrder, PurchaseOrderHistory


@receiver(post_save, sender=PurchaseOrder)
def send_po_notification(sender, instance, created, **kwargs):
    """Send email notification when PO is created or status changes"""
    
    # Determine the action
    if created:
        action = "Created"
        subject = f"New Purchase Order: {instance.po_number}"
    else:
        action = instance.status.title()
        subject = f"Purchase Order {action}: {instance.po_number}"
    
    # Prepare items data
    items = []
    for item in instance.items.all():
        items.append({
            'product_name': item.product_name,
            'product_sku': item.product.sku if item.product else 'N/A',
            'quantity': item.quantity,
            'unit_price': f"{item.unit_price:,.2f}",
            'subtotal': f"{item.subtotal:,.2f}",
        })
    
    # Prepare context
    context = {
        'action': action,
        'po_number': instance.po_number,
        'status': instance.status,
        'supplier_name': instance.supplier_name,
        'order_date': instance.order_date.strftime('%B %d, %Y'),
        'expected_delivery': instance.expected_delivery.strftime('%B %d, %Y'),
        'created_by': instance.created_by.get_full_name() if instance.created_by else 'System',
        'approved_by': instance.approved_by.get_full_name() if instance.approved_by else None,
        'approved_at': instance.approved_at.strftime('%B %d, %Y %I:%M %p') if instance.approved_at else None,
        'received_by': instance.received_by.get_full_name() if instance.received_by else None,
        'received_at': instance.received_at.strftime('%B %d, %Y %I:%M %p') if instance.received_at else None,
        'items': items,
        'total_amount': f"{instance.total_amount:,.2f}",
        'stock_value': f"{instance.stock_value:,.2f}",
        'notes': instance.notes,
        'po_url': f"{settings.FRONTEND_URL}/purchase-orders/{instance.id}" if hasattr(settings, 'FRONTEND_URL') else '#',
    }
    
    # Render HTML email
    html_content = render_to_string('emails/purchase_order.html', context)
    
    # Create plain text version
    text_content = f"""
Purchase Order {action}

PO Number: {instance.po_number}
Status: {instance.status}
Supplier: {instance.supplier_name}
Order Date: {instance.order_date.strftime('%B %d, %Y')}
Expected Delivery: {instance.expected_delivery.strftime('%B %d, %Y')}
Total Amount: ₦{instance.total_amount:,.2f}
Stock Value: ₦{instance.stock_value:,.2f}

Items:
"""
    for item in items:
        text_content += f"\n- {item['product_name']}: {item['quantity']} x ₦{item['unit_price']}"
    
    text_content += "\n\nThis is an automated notification from Kasali Oloshe Inventory Management System."
    
    # Determine recipients
    recipients = [settings.EMAIL_HOST_USER]
    if instance.created_by and instance.created_by.email:
        recipients.append(instance.created_by.email)
    
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
        print(f"✓ Purchase order email sent for {instance.po_number}")
    except Exception as e:
        print(f"✗ Failed to send PO email: {str(e)}")
