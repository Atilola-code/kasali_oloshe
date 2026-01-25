# chat/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
import uuid

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        
        if self.user.is_anonymous:
            await self.close()
            return
        
        # Create a personal channel for this user
        self.user_group_name = f'user_{self.user.id}'
        
        # Join user's personal group
        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send confirmation
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'Connected to chat server',
            'userId': str(self.user.id)
        }))

    async def disconnect(self, close_code):
        if hasattr(self, 'user_group_name'):
            await self.channel_layer.group_discard(
                self.user_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')
        
        if message_type == 'chat_message':
            await self.handle_chat_message(data)
        elif message_type == 'typing_start':
            await self.handle_typing(data, True)
        elif message_type == 'typing_stop':
            await self.handle_typing(data, False)
        elif message_type == 'mark_read':
            await self.handle_mark_read(data)

    async def handle_chat_message(self, data):
        receiver_id = data.get('receiverId')
        message_text = data.get('message')
        
        # Save message to database
        message = await self.save_message(
            sender_id=self.user.id,
            receiver_id=receiver_id,
            message_text=message_text
        )
        
        # Send to receiver ONLY (not back to sender)
        await self.channel_layer.group_send(
            f'user_{receiver_id}',
            {
                'type': 'chat_message_handler',
                'message': message
            }
        )
        
        # Send confirmation to sender ONLY (with the saved message)
        await self.send(text_data=json.dumps({
            'type': 'message_sent',
            'message': message
        }))

    async def chat_message_handler(self, event):
        message = event['message']
        await self.send(text_data=json.dumps({
            'type': 'new_message',
            'message': message
        }))

    async def handle_typing(self, data, is_typing):
        receiver_id = data.get('receiverId')
        
        await self.channel_layer.group_send(
            f'user_{receiver_id}',
            {
                'type': 'typing_indicator',
                'senderId': str(self.user.id),
                'isTyping': is_typing
            }
        )

    async def typing_indicator(self, event):
        await self.send(text_data=json.dumps({
            'type': 'typing_indicator',
            'senderId': event['senderId'],
            'isTyping': event['isTyping']
        }))

    async def handle_mark_read(self, data):
        sender_id = data.get('senderId')
        await self.mark_messages_read(sender_id, self.user.id)

    @database_sync_to_async
    def save_message(self, sender_id, receiver_id, message_text):
        from django.contrib.auth import get_user_model
        from .models import Message
        
        User = get_user_model()
        sender = User.objects.get(id=sender_id)
        receiver = User.objects.get(id=receiver_id)
        
        message = Message.objects.create(
            sender=sender,
            receiver=receiver,
            message=message_text
        )
        
        return message.to_dict()

    @database_sync_to_async
    def mark_messages_read(self, sender_id, receiver_id):
        from django.utils import timezone
        from .models import Message
        
        Message.objects.filter(
            sender_id=sender_id,
            receiver_id=receiver_id,
            is_read=False
        ).update(is_read=True, read_at=timezone.now())