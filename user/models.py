from django.contrib.auth.models import AbstractUser
from django.db import models
from .managers import UserManager

class User(AbstractUser):
    USER_ROLES = (
        ('ADMIN', 'Admin'),
        ('MANAGER', 'Manager'),
        ('CASHIER', 'Cashier'),
    )

    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    username = None
    phone = models.CharField(max_length=11, blank=True, null=True)
    role = models.CharField(max_length=20, choices=USER_ROLES, default='CASHIER')

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return f"{self.email} ({self.role})"
    