from rest_framework import serializers
from .models import Plant
from accounts.models import SellerProfile
from reviews.models import Review


class PlantSellerSerializer(serializers.ModelSerializer):
   
    class Meta:
        model = SellerProfile
        fields = [
            "id",
            "store_name",
            "city",
            "address",
            "latitude",
            "longitude",
            "is_verified",
        ]
        read_only_fields = fields


class PlantSerializer(serializers.ModelSerializer):
   
    seller = PlantSellerSerializer(read_only=True)
    image_url = serializers.SerializerMethodField()
    distance = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()

    class Meta:
        model = Plant
        fields = [
            "id",
            "seller",
            "name",
            "scientific_name",
            "slug",
            "category",
            "description",
            "price",
            "stock_quantity",
            "image",
            "image_url",
            "is_available",
            "distance",
            "average_rating",
            "review_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "slug",
            "seller",
            "image_url",
            "distance",
            "average_rating",
            "review_count",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            
            "image": {"write_only": True, "required": True}
        }

    def get_image_url(self, obj) -> str:
        
        if hasattr(obj, "image") and obj.image:
            return obj.image.url
        return ""

    def get_distance(self, obj) -> float | None:
        
        if hasattr(obj, "distance"):
            return round(obj.distance, 2)
        return None

    def get_average_rating(self, obj) -> float | None:
        reviews = obj.reviews.all()
        if not reviews.exists():
            return None
        total = sum(r.rating for r in reviews)
        return round(total / reviews.count(), 1)

    def get_review_count(self, obj) -> int:
        return obj.reviews.count()

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than zero.")
        return value

    def validate_stock_quantity(self, value):
        if value < 0:
            raise serializers.ValidationError("Stock quantity cannot be negative.")
        return value


class PlantIdentificationSerializer(serializers.Serializer):
    
    image = serializers.ImageField(required=True)

    def validate_image(self, file):
        # 5 MB file size limit
        max_size = 5 * 1024 * 1024
        if file.size > max_size:
            raise serializers.ValidationError("Image file size must be under 5MB.")
        return file