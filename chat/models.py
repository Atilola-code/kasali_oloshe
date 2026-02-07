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
    is_deleted_by_sender = models.BooleanField(default=False)
    is_deleted_by_receiver = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    reaction = models.CharField(max_length=10, null=True, blank=True)  # Store emoji
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['sender', 'receiver']),
            models.Index(fields=['receiver', 'is_read']),
            models.Index(fields=['created_at']),
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
            'reaction': self.reaction,
            'isDeletedBySender': self.is_deleted_by_sender,
            'isDeletedByReceiver': self.is_deleted_by_receiver,
            'createdAt': self.created_at.isoformat(),
            'sender': {
                'id': str(self.sender.id),
                'first_name': self.sender.first_name,
                'last_name': self.sender.last_name,
            }
        }

    def soft_delete(self, user):
        """Soft delete message for a specific user"""
        if user == self.sender:
            self.is_deleted_by_sender = True
        elif user == self.receiver:
            self.is_deleted_by_receiver = True
        
        from django.utils import timezone
        if not self.deleted_at:
            self.deleted_at = timezone.now()
        
        self.save()

    @property
    def is_deleted(self):
        """Check if message is deleted for both users"""
        return self.is_deleted_by_sender and self.is_deleted_by_receiver