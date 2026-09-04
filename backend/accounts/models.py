from django.db import models

# Create your models here.
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

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



class SellerProfile(models.Model):
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name = "seller_profile"
    )

    store_name = models.CharField(max_length=150)
    bio=models.TextField(blank=True)
    address = models.CharField(max_length=280)
    city = models.CharField(max_length=100, db_index=True)

    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-90.0),MaxValueValidator(90.0)]
    )
    longitude = models.DecimalField(
            max_digits=9,
            decimal_places=6,
            validators=[MinValueValidator(-180.0),MaxValueValidator(180.0)]
    )

    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["latitude", "longitude"])
        ]

    def __str__(self):
        return self.store_name

    @property
    def google_maps_embed_url(self):
        return f"https://maps.google.com/maps?q={self.latitude},{self.longitude}&z=15&output=embed"