from django.urls import path
from rest_framework_simplejwt.views import  TokenRefreshView
from .views import RegisterUserView, LoginView, SignupView, UserDetailView, UserListView
from . import views

urlpatterns = [
    path('signup/', SignupView.as_view(), name='signup'),
    path('register/', RegisterUserView.as_view(), name='register_user'),
    path('login/', LoginView.as_view(), name='login_user'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('', UserListView.as_view(), name='list_users'),
    path('<int:pk>/', UserDetailView.as_view(), name='user_detail'),
    path('health/', views.health_check, name='health_check'),

]
