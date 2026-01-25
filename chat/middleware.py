# chat/middleware.py
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from urllib.parse import parse_qs

# DON'T import User or AccessToken at module level - import them inside functions
# This prevents Django from loading models before settings are configured

class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        # Get token from query string
        query_string = scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        token = query_params.get('token', [None])[0]
        
        if token:
            scope['user'] = await self.get_user_from_token(token)
        else:
            scope['user'] = AnonymousUser()
        
        return await super().__call__(scope, receive, send)
    
    @database_sync_to_async
    def get_user_from_token(self, token_string):
        try:
            # Import inside the function to avoid circular imports
            from rest_framework_simplejwt.tokens import AccessToken
            from django.contrib.auth import get_user_model
            
            access_token = AccessToken(token_string)
            user_id = access_token['user_id']
            User = get_user_model()
            user = User.objects.get(id=user_id)
            return user
        except Exception as e:
            print(f"Error authenticating user: {e}")
            from django.contrib.auth.models import AnonymousUser
            return AnonymousUser()