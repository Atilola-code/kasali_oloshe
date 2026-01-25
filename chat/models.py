# chat/models.py
from django.db import models
from django.conf import settings

class Message(models.Model):
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='sent_messages'
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='received_messages'
    )
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['sender', 'receiver']),
            models.Index(fields=['receiver', 'is_read']),
        ]

    def __str__(self):
        return f"{self.sender.username} to {self.receiver.username}: {self.message[:50]}"

    def to_dict(self):
        return {
            'id': self.id,
            'senderId': str(self.sender.id),
            'receiverId': str(self.receiver.id),
            'message': self.message,
            'isRead': self.is_read,
            'readAt': self.read_at.isoformat() if self.read_at else None,
            'createdAt': self.created_at.isoformat(),
            'sender': {
                'id': str(self.sender.id),
                'first_name': self.sender.first_name,
                'last_name': self.sender.last_name,
            }
        }