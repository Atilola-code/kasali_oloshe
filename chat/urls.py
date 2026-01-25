# chat/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('users/', views.get_users, name='chat-users'),
    path('conversation/<str:user_id>/', views.get_conversation, name='chat-conversation'),
    path('message/', views.send_message, name='send-message'),
    path('messages/read/<str:user_id>/', views.mark_messages_read, name='mark-messages-read'),
    path('unread-count/', views.get_unread_count, name='unread-count'),
    path('unread-by-user/', views.get_unread_by_user, name='unread-by-user'),
]

