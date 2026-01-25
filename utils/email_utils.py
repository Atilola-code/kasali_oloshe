# utils/email_utils.py
"""
Utility functions for sending emails
"""
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def send_template_email(subject, template_name, context, recipients, text_template=None):
    """
    Send an email using HTML template with fallback to plain text
    
    Args:
        subject (str): Email subject
        template_name (str): Path to HTML template (e.g., 'emails/low_stock_alert.html')
        context (dict): Context data for template
        recipients (list): List of recipient email addresses
        text_template (str, optional): Path to plain text template
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        # Render HTML content
        html_content = render_to_string(template_name, context)
        
        # Render or generate plain text content
        if text_template:
            text_content = render_to_string(text_template, context)
        else:
            # Strip HTML tags for basic plain text version
            import re
            text_content = re.sub('<[^<]+?>', '', html_content)
        
        # Create email
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients,
        )
        email.attach_alternative(html_content, "text/html")
        
        # Send
        email.send(fail_silently=False)
        logger.info(f"✓ Email sent: {subject} to {recipients}")
        return True
        
    except Exception as e:
        logger.error(f"✗ Failed to send email: {subject}. Error: {str(e)}")
        return False


def send_low_stock_alert(product):
    """Send low stock alert email"""
    context = {
        'product_name': product.name,
        'sku': product.sku,
        'category': product.get_category_display(),
        'quantity': product.quantity,
        'threshold': product.low_stock_threshold,
        'stock_value': f"{product.stock_value:,.2f}",
        'dashboard_url': f"{settings.FRONTEND_URL}/inventory",
    }
    
    return send_template_email(
        subject=f"⚠️ Low Stock Alert: {product.name}",
        template_name='emails/low_stock_alert.html',
        context=context,
        recipients=[settings.EMAIL_HOST_USER, 'hammedolasupo03@gmail.com']
    )


def send_purchase_order_email(purchase_order, action="Created"):
    """Send purchase order notification"""
    items = [{
        'product_name': item.product_name,
        'product_sku': item.product.sku if item.product else 'N/A',
        'quantity': item.quantity,
        'unit_price': f"{item.unit_price:,.2f}",
        'subtotal': f"{item.subtotal:,.2f}",
    } for item in purchase_order.items.all()]
    
    context = {
        'action': action,
        'po_number': purchase_order.po_number,
        'status': purchase_order.status,
        'supplier_name': purchase_order.supplier_name,
        'order_date': purchase_order.order_date.strftime('%B %d, %Y'),
        'expected_delivery': purchase_order.expected_delivery.strftime('%B %d, %Y'),
        'created_by': purchase_order.created_by.get_full_name() if purchase_order.created_by else 'System',
        'approved_by': purchase_order.approved_by.get_full_name() if purchase_order.approved_by else None,
        'approved_at': purchase_order.approved_at.strftime('%B %d, %Y %I:%M %p') if purchase_order.approved_at else None,
        'received_by': purchase_order.received_by.get_full_name() if purchase_order.received_by else None,
        'received_at': purchase_order.received_at.strftime('%B %d, %Y %I:%M %p') if purchase_order.received_at else None,
        'items': items,
        'total_amount': f"{purchase_order.total_amount:,.2f}",
        'stock_value': f"{purchase_order.stock_value:,.2f}",
        'notes': purchase_order.notes,
        'po_url': f"{settings.FRONTEND_URL}/purchase-orders/{purchase_order.id}",
    }
    
    recipients = [settings.EMAIL_HOST_USER]
    if purchase_order.created_by and purchase_order.created_by.email:
        recipients.append(purchase_order.created_by.email)
    
    return send_template_email(
        subject=f"Purchase Order {action}: {purchase_order.po_number}",
        template_name='emails/purchase_order.html',
        context=context,
        recipients=recipients
    )


def send_sales_receipt_email(sale):
    """Send sales receipt email"""
    items = [{
        'product_name': item.product.name if item.product else 'N/A',
        'quantity': item.quantity,
        'unit_price': f"{item.unit_price:,.2f}",
        'subtotal': f"{item.subtotal:,.2f}",
    } for item in sale.items.all()]
    
    # Calculate VAT percentage
    vat_percent = 0
    if sale.vat_amount > 0 and sale.subtotal > 0:
        vat_percent = (sale.vat_amount / (sale.subtotal - sale.discount_amount)) * 100
    
    context = {
        'invoice_id': sale.invoice_id,
        'date': sale.date.strftime('%B %d, %Y %I:%M %p'),
        'customer_name': sale.customer_name or 'Walk-in Customer',
        'cashier_name': sale.cashier.get_full_name() if sale.cashier else 'System',
        'payment_method': sale.get_payment_method_display(),
        'items': items,
        'subtotal': f"{sale.subtotal:,.2f}",
        'discount_amount': f"{sale.discount_amount:,.2f}",
        'vat_amount': f"{sale.vat_amount:,.2f}",
        'vat_percent': f"{vat_percent:.1f}",
        'total_amount': f"{sale.total_amount:,.2f}",
        'amount_paid': f"{sale.amount_paid:,.2f}",
        'change_due': f"{sale.change_due:,.2f}",
        'outstanding_amount': f"{sale.total_amount - sale.amount_paid:,.2f}",
        'contact_email': settings.EMAIL_HOST_USER,
    }
    
    return send_template_email(
        subject=f"Receipt for Invoice {sale.invoice_id}",
        template_name='emails/sales_receipt.html',
        context=context,
        recipients=[settings.EMAIL_HOST_USER]
    )