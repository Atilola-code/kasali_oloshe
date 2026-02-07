# chat/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from .models import Message
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Message)
def send_message_notification_email(sender, instance, created, **kwargs):
    """
    Send email notification when a new message is created
    Only send if receiver has email configured
    """
    if not created:
        return
    
    receiver = instance.receiver
    
    # Check if receiver has email
    if not receiver.email:
        logger.info(f"Receiver {receiver.username} has no email configured, skipping notification")
        return
    
    # Prepare email context
    context = {
        'receiver_name': receiver.get_full_name() or receiver.username,
        'sender_name': instance.sender.get_full_name() or instance.sender.username,
        'message_preview': instance.message[:100] + ('...' if len(instance.message) > 100 else ''),
        'chat_url': f"{settings.FRONTEND_URL}/live-chat",
        'timestamp': instance.created_at.strftime('%B %d, %Y at %I:%M %p'),
    }
    
    # Render HTML email
    html_content = render_to_string('emails/new_message_notification.html', context)
    
    # Create plain text version
    text_content = f"""
New Message from {context['sender_name']}

You have received a new message on Kasali Oloshe Inventory Management:

From: {context['sender_name']}
Time: {context['timestamp']}

Message:
{context['message_preview']}

View your messages: {context['chat_url']}

---
Kasali Oloshe Inventory Management System
    """
    
    subject = f"New message from {context['sender_name']}"
    
    # Send email
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[receiver.email],
    )
    email.attach_alternative(html_content, "text/html")
    
    try:
        email.send(fail_silently=False)
        logger.info(f"✓ Message notification email sent to {receiver.email}")
    except Exception as e:
        logger.error(f"✗ Failed to send message notification email: {str(e)}")