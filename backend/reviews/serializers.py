from rest_framework import serializers
from .models import Review
from orders.models import Order, OrderItem


class ReviewBuyerSerializer(serializers.Serializer):
    """Publicly visible buyer info attached to reviews."""
    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)


class ReviewSerializer(serializers.ModelSerializer):
    """
    Handles listing reviews for a plant, as well as creating reviews.
    The user is populated automatically from request.user in perform_create.
    """
    user = ReviewBuyerSerializer(read_only=True)

    class Meta:
        model = Review
        fields = [
            "id",
            "plant",
            "user",
            "rating",
            "comment",
            "created_at",
        ]
        read_only_fields = ["id", "user", "created_at"]

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be an integer between 1 and 5.")
        return value

    def validate(self, attrs):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required to review a plant.")

        user = request.user
        plant = attrs.get("plant")

        # 1. Prevent duplicate reviews (handled on create only)
        if self.instance is None:
            if Review.objects.filter(user=user, plant=plant).exists():
                raise serializers.ValidationError(
                    {"detail": "You have already submitted a review for this plant."}
                )

        # 2. Verify verified purchase: User must have an order with this plant that is not PENDING/CANCELLED
        has_purchased = OrderItem.objects.filter(
            order__buyer=user,
            plant=plant,
            order__status__in=[
                Order.OrderStatus.PAID,
                Order.OrderStatus.SHIPPED,
                Order.OrderStatus.DELIVERED,
            ],
        ).exists()

        if not has_purchased:
            raise serializers.ValidationError(
                {"detail": "You can only review plants you have purchased and paid for."}
            )

        return attrs