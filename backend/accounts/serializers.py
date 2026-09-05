from .models import CustomUser,SellerProfile
from rest_framework import serializers

class SellerProfileSerializer(serializers.ModelSerializer):
    google_maps_embed_url = serializers.ReadOnlyField()

    class Meta:
        model = SellerProfile
        fields = [
            "id",
            "store_name",
            "bio",
            "address",
            "city",
            "latitude",
            "longitude",
            "is_verified",
            "google_maps_embed_url",
            "created_at",
        ]

        read_only_fields = ["id", "is_verified", "created_at"]


class CustomUserSerializer(serializers.ModelSerializer):
    seller_profile = SellerProfileSerializer(read_only=True)
    password = serializers.CharField(write_only=True,min_length=8)

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "email",
            "username",
            "password",
            "role",
            "phone_number",
            "seller_profile",
        ]

        read_only_fields = ["id"]

        def create(self, validated_data):
            return CustomUser.objects.create_user(**validated_data)

class UserRegistrationSerializer(serializers.ModelSerializer):

    password = serializers.CharField(write_only=True,min_length=8)
    store_name=serializers.CharField(write_only=True,required=False)
    address=serializers.CharField(write_only=True,required=False)
    city=serializers.CharField(write_only=True,required=False)
    latitude=serializers.DecimalField(
        max_digits=9, decimal_places=6, write_only=True, required=False
    )
    longitude=serializers.DecimalField(
            max_digits=9, decimal_places=6, write_only=True, required=False
    )

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "email",
            "username",
            "password",
            "role",
            "phone_number",
            "store_name",
            "address",
            "city",
            "latitude",
            "longitude",
        ]

    def validate(self, attrs):
        if attrs.get("role") == CustomUser.Role.SELLER:
            required_seller_fields = ["store_name", "address", "city", "latitude", "longitude"]
            missing = [field for field in required_seller_fields if not attrs.get(field)]
            if missing:
                raise serializers.ValidationError(
                    {field: "This field is required for seller registration." for field in missing}
                )
        return attrs

    def create(self, validated_data):
        seller_data = {
            "store_name": validated_data.pop("store_name", None),
            "address": validated_data.pop("address", None),
            "city": validated_data.pop("city", None),
            "latitude": validated_data.pop("latitude", None),
            "longitude": validated_data.pop("longitude", None),
        }

        user = CustomUser.objects.create_user(**validated_data)

        if user.role == CustomUser.Role.SELLER:
            SellerProfile.objects.create(user=user, **seller_data)

        return user

