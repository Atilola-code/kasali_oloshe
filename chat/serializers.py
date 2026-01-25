# chat/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Message

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email', 'role']

class SenderSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name']

class MessageSerializer(serializers.ModelSerializer):
    sender = SenderSerializer(read_only=True)
    senderId = serializers.CharField(source='sender.id', read_only=True)
    receiverId = serializers.CharField(source='receiver.id', read_only=True)
    isRead = serializers.BooleanField(source='is_read', read_only=True)
    readAt = serializers.DateTimeField(source='read_at', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    
    class Meta:
        model = Message
        fields = [
            'id', 'senderId', 'receiverId', 'message', 
            'isRead', 'readAt', 'createdAt', 'sender'
        ]