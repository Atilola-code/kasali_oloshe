# chat/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # User endpoints
    path('users/', views.get_users, name='chat-users'),
    
    # Message endpoints
    path('conversation/<str:user_id>/', views.get_conversation, name='chat-conversation'),
    path('conversation/<str:user_id>/search/', views.search_messages, name='search-messages'),
    path('message/', views.send_message, name='send-message'),
    path('message/<int:message_id>/read/', views.mark_message_read, name='mark-message-read'),
    path('message/<int:message_id>/react/', views.react_to_message, name='react-to-message'),
    path('message/<int:message_id>/delete/', views.delete_message, name='delete-message'),
    
    # Bulk operations
    path('messages/read/<str:user_id>/', views.mark_messages_read, name='mark-messages-read'),
    
    # Unread counts
    path('unread-count/', views.get_unread_count, name='unread-count'),
    path('unread-by-user/', views.get_unread_by_user, name='unread-by-user'),
]