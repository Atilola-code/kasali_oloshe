from rest_framework_simplejwt.serializers import  TokenObtainPairSerializer
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        
        # Add custom claims
        token['email'] = user.email
        token['first_name'] = user.first_name
        token['last_name'] = user.last_name
        token['role'] = user.role
        token['phone'] = user.phone if user.phone else ''
        
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        
        # Add user info to response
        data['user'] = {
            'id': self.user.id,
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
            'email': self.user.email,
            'phone': self.user.phone,
            'role': self.user.role,
        }
        return data
    
class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)
    confirm_password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ['id','first_name','last_name','email','role','phone','password','confirm_password',]
        read_only_fields = ['id',]  # Prevent users from setting these manually during signup

    def validate(self, attrs):
        # Validate password match and strength
        if attrs.get("password") != attrs.get("confirm_password"):
            raise serializers.ValidationError({"password": "Passwords do not match."})

        # Password strength check
        validate_password(attrs.get("password"))
        return attrs

    def create(self, validated_data):
        #  Remove confirm_password since it's not in the model
        validated_data.pop("confirm_password", None)
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def to_representation(self, instance):
        # Exclude password fields from the serialized output
        rep = super().to_representation(instance)
        rep.pop('password', None)
        rep.pop('confirm_password', None)
        return rep
    
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

