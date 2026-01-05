from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.contrib.auth import authenticate
from rest_framework_simplejwt.views import TokenObtainPairView
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse
from .models import User
from .serializers import UserSerializer, LoginSerializer, CustomTokenObtainPairSerializer
from .permissions import IsAdminOrManager
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

class RegisterUserView(generics.CreateAPIView):
    """
    Admin-only endpoint to register new users (Cashier, Manager, etc.)
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdminOrManager]

    @extend_schema(
        summary="Register a new user (Admin or Manager)",
        description="Allows  Admin and manager to register a new Cashier or Manager account. "
                    "This endpoint is protected and only accessible to Admin and manager users.",
        tags=["User Management"],
        examples=[
            OpenApiExample(
                "Register Example",
                summary="Register a new cashier",
                value={
                    "first_name": "Adeola",
                    "last_name": "Bamidele",
                    "email": "cashier1@inventory.com",
                    "password": "StrongPass123!",
                    "confirm_password": "StrongPass123!",
                    "phone": "08012345678",
                    "role": "CASHIER"
                },
            )
        ],
        responses={201: UserSerializer}
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class LoginView(generics.CreateAPIView):
    """
    Login endpoint for any registered user (Admin, Manager, or Cashier)
    """
    serializer_class = LoginSerializer
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        summary="Login user (Admin, Manager, or Cashier)",
        description=(
            "Authenticates a user using their **email** and **password**. "
            "Returns JWT access and refresh tokens upon successful login."
        ),
        tags=["User Management"],
        examples=[
            OpenApiExample(
                "Login Example",
                summary="Login with email and password",
                value={
                    "email": "cashier1@inventory.com",
                    "password": "StrongPass123!"
                },
            )
        ],
        responses={
            200: OpenApiResponse(
                description="Successful login with tokens and user details",
                examples=[
                    OpenApiExample(
                        "Success Response",
                        value={
                            "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
                            "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
                            "user": {
                                "id": 1,
                                "first_name": "John",
                                "last_name": "Doe",
                                "email": "cashier1@inventory.com",
                                "phone": "08012345678",
                                "role": "CASHIER"
                            }
                        }
                    )
                ]
            ),
            401: OpenApiResponse(
                description="Invalid credentials",
                examples=[
                    OpenApiExample(
                        "Invalid Credentials",
                        value={"detail": "Invalid email or password"}
                    )
                ]
            ),
        }
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data.get("email")
        password = serializer.validated_data.get("password")

        user = authenticate(request, email=email, password=password)
        if not user:
            return Response({"detail": "Invalid email or password"}, status=status.HTTP_401_UNAUTHORIZED)

        # Use custom token serializer to generate tokens
        token_serializer = CustomTokenObtainPairSerializer()
        token = token_serializer.get_token(user)
        
        data = {
            "refresh": str(token),
            "access": str(token.access_token),
            "user": {
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "phone": user.phone,
                "role": user.role,
            }
        }
        return Response(data, status=status.HTTP_200_OK)

class UserListView(generics.ListAPIView):
    """
    List all users (Admin and Manager only)
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdminOrManager]

class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a user instance.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdminOrManager]

    @extend_schema(
        summary="Delete a user",
        description="Delete a user (Admin or Manager only)",
        tags=["User Management"],
        responses={
            204: OpenApiResponse(description="User deleted successfully"),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="User not found"),
        }
    )
    def delete(self, request, *args, **kwargs):
        # Prevent users from deleting themselves
        user_to_delete = self.get_object()
        if user_to_delete.id == request.user.id:
            return Response(
                {"detail": "You cannot delete your own account"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().delete(request, *args, **kwargs)
