from django.urls import path
from .views import RegisterUserView, LoginView, UserDetailView, UserListView

urlpatterns = [
    path('register/', RegisterUserView.as_view(), name='register_user'),
    path('login/', LoginView.as_view(), name='login_user'),
    path('', UserListView.as_view(), name='list_users'),
    path('<int:pk>/', UserDetailView.as_view(), name='user_detail'),
]
