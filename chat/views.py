# chat/views.py
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.db.models import Q, Count
from django.utils import timezone
from .models import Message
from .serializers import UserSerializer, MessageSerializer

User = get_user_model()

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_users(request):
    """Get all users except the current user"""
    users = User.objects.exclude(id=request.user.id).filter(
        is_active=True
    ).order_by('first_name')
    
    serializer = UserSerializer(users, many=True)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_conversation(request, user_id):
    """Get conversation between current user and specified user"""
    messages = Message.objects.filter(
        Q(sender=request.user, receiver_id=user_id) |
        Q(sender_id=user_id, receiver=request.user)
    ).select_related('sender').order_by('created_at')
    
    serializer = MessageSerializer(messages, many=True)
    return Response(serializer.data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_message(request):
    """Send a message (also saves to database)"""
    receiver_id = request.data.get('receiverId')
    message_text = request.data.get('message')
    
    if not receiver_id or not message_text:
        return Response(
            {'error': 'receiverId and message are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        receiver = User.objects.get(id=receiver_id)
    except User.DoesNotExist:
        return Response(
            {'error': 'Receiver not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    message = Message.objects.create(
        sender=request.user,
        receiver=receiver,
        message=message_text
    )
    
    serializer = MessageSerializer(message)
    return Response(serializer.data, status=status.HTTP_201_CREATED)

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def mark_messages_read(request, user_id):
    """Mark all messages from a specific user as read"""
    Message.objects.filter(
        sender_id=user_id,
        receiver=request.user,
        is_read=False
    ).update(is_read=True, read_at=timezone.now())
    
    return Response({'success': True})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_unread_count(request):
    """Get total unread message count"""
    count = Message.objects.filter(
        receiver=request.user,
        is_read=False
    ).count()
    
    return Response({'count': count})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_unread_by_user(request):
    """Get unread message count per user"""
    unread_messages = Message.objects.filter(
        receiver=request.user,
        is_read=False
    ).values('sender_id').annotate(count=Count('id'))
    
    unread_by_user = {
        str(item['sender_id']): item['count'] 
        for item in unread_messages
    }
    
    return Response(unread_by_user)