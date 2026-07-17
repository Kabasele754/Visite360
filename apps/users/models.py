from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=32, blank=True)
    is_customer = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    stripe_customer_id = models.CharField(max_length=255, blank=True, db_index=True)
    preferred_currency = models.CharField(max_length=8, default="USD")

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    @property
    def email_verified(self):
        return self.email_verified_at is not None

    def __str__(self):
        return self.email
