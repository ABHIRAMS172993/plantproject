from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from plants.models import Plant


class Review(models.Model):
    plant = models.ForeignKey(
        Plant, 
        on_delete=models.CASCADE, 
        related_name="reviews"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name="reviews"
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rate 1 to 5 stars"
    )
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            
            models.UniqueConstraint(fields=["plant", "user"], name="unique_user_plant_review")
        ]

    def __str__(self):
        return f"{self.rating}★ by {self.user.username} on {self.plant.name}"