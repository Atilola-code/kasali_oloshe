# chat/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

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
            await self.handle_chat_message_broadcast(data)
        elif message_type == 'typing_start':
            await self.handle_typing(data, True)
        elif message_type == 'typing_stop':
            await self.handle_typing(data, False)
        elif message_type == 'mark_read':
            await self.handle_mark_read(data)
        elif message_type == 'message_read':
            await self.handle_message_read(data)
        elif message_type == 'message_reaction':
            await self.handle_message_reaction(data)
        elif message_type == 'message_delete':
            await self.handle_message_delete(data)

    async def handle_chat_message_broadcast(self, data):
        """Broadcast message to receiver without saving (HTTP API handles saving)"""
        receiver_id = data.get('receiverId')
        message_text = data.get('message')
        message_id = data.get('messageId')
        
        # Broadcast to receiver
        await self.channel_layer.group_send(
            f'user_{receiver_id}',
            {
                'type': 'chat_message_handler',
                'message': {
                    'id': message_id,
                    'senderId': str(self.user.id),
                    'receiverId': receiver_id,
                    'message': message_text,
                    'isRead': False,
                    'createdAt': data.get('createdAt'),
                    'sender': {
                        'first_name': self.user.first_name,
                        'last_name': self.user.last_name,
                    }
                }
            }
        )

    async def chat_message_handler(self, event):
        """Receive message from room group and send to WebSocket"""
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

    async def handle_message_read(self, data):
        """Handle single message read receipt"""
        message_id = data.get('messageId')
        receiver_id = data.get('receiverId')
        
        # Broadcast read receipt to sender
        await self.channel_layer.group_send(
            f'user_{receiver_id}',
            {
                'type': 'message_read_handler',
                'messageId': message_id,
                'readBy': str(self.user.id)
            }
        )

    async def message_read_handler(self, event):
        """Send read receipt to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'message_read',
            'messageId': event['messageId'],
            'readBy': event['readBy']
        }))

    async def handle_message_reaction(self, data):
        """Handle message reaction"""
        message_id = data.get('messageId')
        reaction = data.get('reaction')
        receiver_id = data.get('receiverId')
        
        # Broadcast reaction to other user
        await self.channel_layer.group_send(
            f'user_{receiver_id}',
            {
                'type': 'message_reaction_handler',
                'messageId': message_id,
                'reaction': reaction,
                'reactedBy': str(self.user.id)
            }
        )

    async def message_reaction_handler(self, event):
        """Send reaction update to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'message_reaction',
            'messageId': event['messageId'],
            'reaction': event['reaction'],
            'reactedBy': event['reactedBy']
        }))

    async def handle_message_delete(self, data):
        """Handle message deletion"""
        message_id = data.get('messageId')
        receiver_id = data.get('receiverId')
        
        # Broadcast deletion to other user
        await self.channel_layer.group_send(
            f'user_{receiver_id}',
            {
                'type': 'message_delete_handler',
                'messageId': message_id,
                'deletedBy': str(self.user.id)
            }
        )

    async def message_delete_handler(self, event):
        """Send deletion update to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'message_deleted',
            'messageId': event['messageId'],
            'deletedBy': event['deletedBy']
        }))

    @database_sync_to_async
    def mark_messages_read(self, sender_id, receiver_id):
        from django.utils import timezone
        from .models import Message
        
        Message.objects.filter(
            sender_id=sender_id,
            receiver_id=receiver_id,
            is_read=False
        ).update(is_read=True, read_at=timezone.now())