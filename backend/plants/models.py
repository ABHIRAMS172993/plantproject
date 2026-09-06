from django.db import models
from django.utils.text import slugify
from cloudinary.models import CloudinaryField
from accounts.models import SellerProfile


class Plant(models.Model):

    class PlantCategory(models.TextChoices):
        INDOOR = "INDOOR", "Indoor"
        OUTDOOR = "OUTDOOR", "Outdoor"
        SUCCULENT = "SUCCULENT", "Succulent & Cactus"
        FLOWERING = "FLOWERING", "Flowering"
        MEDICINAL = "MEDICINAL", "Medicinal & Herbs"

    seller = models.ForeignKey(
        SellerProfile,
        on_delete=models.CASCADE,
        related_name="plants"
    )

    name = models.CharField(
        max_length=150,
        db_index=True
    )

    scientific_name = models.CharField(
        max_length=150,
        blank=True,
        db_index=True
    )

    slug = models.SlugField(
        max_length=180,
        unique=True,
        blank=True
    )

    category = models.CharField(
        max_length=20,
        choices=PlantCategory.choices,
        db_index=True
    )

    description = models.TextField()

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        db_index=True
    )

    stock_quantity = models.PositiveIntegerField(
        default=1
    )

    image = CloudinaryField("image")

    is_available = models.BooleanField(
        default=True,
        db_index=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ["-created_at"]

        indexes = [
            models.Index(fields=["category", "price"]),
            models.Index(fields=["is_available", "stock_quantity"]),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(
                f"{self.name}-{self.seller.id}-{self.pk or ''}"
            )

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} - ₹{self.price} ({self.seller.store_name})"