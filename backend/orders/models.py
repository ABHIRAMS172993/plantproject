from django.db import models
from django.conf import settings 
from plants.models import Plant 
# Create your models here.

class Order(models.Model):
    class OrderStatus(models.TextChoices):
        PENDING = "PENDING", "Pending Payment"
        PAID = "PAID", "Payment Successful"
        SHIPPED = "SHIPPED", "Shipped"
        DELIVERED = "DELIVERED", "Delivered"
        CANCELLED = "CANCELLED", "Cancelled"

    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name="orders"
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20, 
        choices=OrderStatus.choices, 
        default=OrderStatus.PENDING,
        db_index=True
    )
    
    shipping_address = models.CharField(max_length=255)
    shipping_city = models.CharField(max_length=100)
    shipping_postal_code = models.CharField(max_length=20)
    contact_phone = models.CharField(max_length=15)

    stripe_payment_intent_id = models.CharField(
        max_length=100,
        unique=True,
        blank=True,
        null=True
    )

    stripe_checkout_session_id = models.CharField(
        max_length=100,
        unique=True,
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.id} - {self.buyer.email} ({self.status})"


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order, 
        on_delete=models.CASCADE, 
        related_name="items"
    )
    plant = models.ForeignKey(
        Plant, 
        on_delete=models.PROTECT, 
        related_name="order_items"
    )
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.quantity}x {self.plant.name} (Order #{self.order.id})"

    @property
    def subtotal(self):
        return self.price_at_purchase * self.quantity
