from django.db import models

# Create your models here.
from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    class Role(models.TextChoices):
        BUYER = "BUYER", "Buyer"
        SELLER = "SELLER", "Seller"

    email = models.EmailField(unique=True)
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.BUYER
    )
    phone_number=models.CharField(max_length=15,blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"] #Will be useful when creating a superuser

    def __str__(self):
        return f"{self.email} ({self.role})"

    @property
    def is_seller(self):
        return self.role == self.Role.SELLER