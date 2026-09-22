from django.contrib.auth.models import AbstractUser
from django.db import models

from accounts.managers import CustomUserManager


class User(AbstractUser):
    """
    Custom user model with email as the login identifier instead of username.
    Swap/extend fields here rather than bolting a profile model on later —
    changing AUTH_USER_MODEL after the first migration is painful.
    """

    username = None
    email = models.EmailField(unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    class Meta:
        managed = False

    def __str__(self):
        return self.email
