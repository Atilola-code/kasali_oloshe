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
    # Exclude messages deleted by current user
    messages = Message.objects.filter(
        Q(sender=request.user, receiver_id=user_id, is_deleted_by_sender=False) |
        Q(sender_id=user_id, receiver=request.user, is_deleted_by_receiver=False)
    ).select_related('sender').order_by('created_at')
    
    serializer = MessageSerializer(messages, many=True)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_messages(request, user_id):
    """Search messages in a conversation"""
    search_query = request.query_params.get('q', '').strip()
    
    if not search_query:
        return Response({'results': []})
    
    # Search in conversation with the specified user
    messages = Message.objects.filter(
        Q(sender=request.user, receiver_id=user_id, is_deleted_by_sender=False) |
        Q(sender_id=user_id, receiver=request.user, is_deleted_by_receiver=False)
    ).filter(
        message__icontains=search_query
    ).select_related('sender').order_by('-created_at')[:50]  # Limit to 50 results
    
    serializer = MessageSerializer(messages, many=True)
    return Response({'results': serializer.data})

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
    updated = Message.objects.filter(
        sender_id=user_id,
        receiver=request.user,
        is_read=False,
        is_deleted_by_receiver=False
    ).update(is_read=True, read_at=timezone.now())
    
    return Response({'success': True, 'updated': updated})

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def mark_message_read(request, message_id):
    """Mark a specific message as read"""
    try:
        message = Message.objects.get(
            id=message_id,
            receiver=request.user
        )
        message.is_read = True
        message.read_at = timezone.now()
        message.save()
        
        serializer = MessageSerializer(message)
        return Response(serializer.data)
    except Message.DoesNotExist:
        return Response(
            {'error': 'Message not found'},
            status=status.HTTP_404_NOT_FOUND
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def react_to_message(request, message_id):
    """Add or update reaction to a message"""
    reaction = request.data.get('reaction', '').strip()
    
    try:
        message = Message.objects.get(id=message_id)
        
        # Only sender or receiver can react
        if request.user not in [message.sender, message.receiver]:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Update or remove reaction
        if reaction:
            message.reaction = reaction
        else:
            message.reaction = None
        
        message.save()
        
        serializer = MessageSerializer(message)
        return Response(serializer.data)
    except Message.DoesNotExist:
        return Response(
            {'error': 'Message not found'},
            status=status.HTTP_404_NOT_FOUND
        )

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_message(request, message_id):
    """Soft delete a message"""
    try:
        message = Message.objects.get(id=message_id)
        
        # Only sender or receiver can delete
        if request.user not in [message.sender, message.receiver]:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Soft delete
        message.soft_delete(request.user)
        
        # If deleted by both users, actually delete from database
        if message.is_deleted:
            message.delete()
            return Response({'success': True, 'permanently_deleted': True})
        
        return Response({'success': True, 'permanently_deleted': False})
    except Message.DoesNotExist:
        return Response(
            {'error': 'Message not found'},
            status=status.HTTP_404_NOT_FOUND
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_unread_count(request):
    """Get total unread message count"""
    count = Message.objects.filter(
        receiver=request.user,
        is_read=False,
        is_deleted_by_receiver=False
    ).count()
    
    return Response({'count': count})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_unread_by_user(request):
    """Get unread message count per user"""
    unread_messages = Message.objects.filter(
        receiver=request.user,
        is_read=False,
        is_deleted_by_receiver=False
    ).values('sender_id').annotate(count=Count('id'))
    
    unread_by_user = {
        str(item['sender_id']): item['count'] 
        for item in unread_messages
    }
    
    return Response(unread_by_user)