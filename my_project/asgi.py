# my_project/asgi.py
import os
import django
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator

# Set default settings module BEFORE importing anything Django-related
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_project.settings')

# Initialize Django
django.setup()

# Now import the ASGI application and your middleware
from django.core.asgi import get_asgi_application
from chat.middleware import JWTAuthMiddleware
import chat.routing

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AllowedHostsOriginValidator(
        JWTAuthMiddleware(
            URLRouter(
                chat.routing.websocket_urlpatterns
            )
        )
    ),
})