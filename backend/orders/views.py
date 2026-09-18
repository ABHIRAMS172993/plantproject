import stripe
from django.conf import settings
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Order, OrderItem
from .serializers import OrderSerializer, CreateOrderSerializer
from plants.models import Plant
from accounts.permissions import IsSeller

# Configure Stripe Secret Key
stripe.api_key = settings.STRIPE_SECRET_KEY


class BuyerOrderListView(generics.ListAPIView):
    """
    GET /api/orders/
    Lists all orders placed by the authenticated buyer.
    """
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (
            Order.objects.filter(buyer=self.request.user)
            .prefetch_related("items__plant__seller")
            .order_by("-created_at")
        )


class BuyerOrderDetailView(generics.RetrieveAPIView):
    """
    GET /api/orders/<int:pk>/
    Fetch an individual order detail for confirmation pages.
    """
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(buyer=self.request.user).prefetch_related("items__plant__seller")


class CreateStripePaymentIntentView(APIView):
    """
    POST /api/orders/checkout/
    1. Locks selected plants and validates inventory.
    2. Computes order total securely on the server.
    3. Creates a Stripe PaymentIntent.
    4. Records the pending Order and OrderItems.
    5. Returns client_secret and publishable key for React Stripe Elements.
    """
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = CreateOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        items_input = data["items"]
        plant_ids = [item["plant_id"] for item in items_input]

        # Lock rows to prevent race conditions during checkout
        plants = Plant.objects.select_for_update().filter(id__in=plant_ids, is_available=True)
        plant_map = {p.id: p for p in plants}

        if len(plant_map) != len(plant_ids):
            return Response(
                {"error": "One or more selected plants are unavailable."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        total_amount = 0
        order_items_to_create = []

        for item in items_input:
            plant = plant_map[item["plant_id"]]
            quantity = item["quantity"]

            if plant.stock_quantity < quantity:
                return Response(
                    {"error": f"Insufficient stock for {plant.name}. Available: {plant.stock_quantity}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            item_subtotal = plant.price * quantity
            total_amount += item_subtotal
            order_items_to_create.append(
                {"plant": plant, "price": plant.price, "quantity": quantity}
            )

        # Stripe amounts are in cents/smallest currency unit (e.g., $10.00 -> 1000)
        stripe_amount = int(total_amount * 100)

        # Pre-create the local Order entry to attach its ID into Stripe metadata
        order = Order.objects.create(
            buyer=request.user,
            total_amount=total_amount,
            shipping_address=data["shipping_address"],
            shipping_city=data["shipping_city"],
            shipping_postal_code=data["shipping_postal_code"],
            contact_phone=data["contact_phone"],
            status=Order.OrderStatus.PENDING,
        )

        for item_data in order_items_to_create:
            OrderItem.objects.create(
                order=order,
                plant=item_data["plant"],
                price_at_purchase=item_data["price"],
                quantity=item_data["quantity"],
            )

        try:
            intent = stripe.PaymentIntent.create(
                amount=stripe_amount,
                currency=getattr(settings, "STRIPE_CURRENCY", "usd"),
                metadata={
                    "order_id": str(order.id),
                    "buyer_id": str(request.user.id),
                    "buyer_email": request.user.email,
                },
                receipt_email=request.user.email,
                automatic_payment_methods={"enabled": True},
            )

            # Store the PaymentIntent ID on the order
            order.stripe_payment_intent_id = intent["id"]
            order.save(update_fields=["stripe_payment_intent_id"])

        except stripe.error.StripeError as e:
            return Response(
                {"error": f"Stripe gateway error: {e.user_message or str(e)}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response({
            "order_id": order.id,
            "client_secret": intent["client_secret"],
            "amount": float(total_amount),
            "currency": getattr(settings, "STRIPE_CURRENCY", "usd"),
            "stripe_publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
        }, status=status.HTTP_201_CREATED)


class VerifyPaymentView(APIView):
    """
    POST /api/orders/verify-payment/
    Manual fallback called by React after stripe.confirmPayment succeeds.
    """
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        payment_intent_id = request.data.get("payment_intent_id")

        if not payment_intent_id:
            return Response(
                {"error": "payment_intent_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Query Stripe to verify real-time status
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)

            if intent.status != "succeeded":
                return Response(
                    {"error": f"Payment not completed. Current status: {intent.status}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            order = Order.objects.select_for_update().get(
                stripe_payment_intent_id=payment_intent_id,
                buyer=request.user,
            )

            if order.status == Order.OrderStatus.PAID:
                return Response({"message": "Payment already processed.", "order_id": order.id})

            order.status = Order.OrderStatus.PAID
            order.save(update_fields=["status"])

            # Decrement inventory
            for item in order.items.select_related("plant"):
                plant = item.plant
                plant.stock_quantity = max(0, plant.stock_quantity - item.quantity)
                if plant.stock_quantity == 0:
                    plant.is_available = False
                plant.save(update_fields=["stock_quantity", "is_available"])

            return Response({
                "status": "Payment verified successfully",
                "order_id": order.id,
            }, status=status.HTTP_200_OK)

        except stripe.error.StripeError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Order.DoesNotExist:
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(APIView):
    """
    POST /api/orders/webhook/
    Stripe Webhook handler: ensures inventory and status updates succeed
    even if the buyer closes their browser immediately after payment.
    """
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def post(self, request):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
        endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        except (ValueError, stripe.error.SignatureVerificationError):
            return HttpResponse(status=status.HTTP_400_BAD_REQUEST)

        # Handle successful payment completion
        if event["type"] == "payment_intent.succeeded":
            intent = event["data"]["object"]
            order_id = intent.get("metadata", {}).get("order_id")

            if order_id:
                try:
                    order = Order.objects.select_for_update().get(pk=order_id)
                    if order.status != Order.OrderStatus.PAID:
                        order.status = Order.OrderStatus.PAID
                        order.stripe_payment_intent_id = intent["id"]
                        order.save(update_fields=["status", "stripe_payment_intent_id"])

                        for item in order.items.select_related("plant"):
                            plant = item.plant
                            plant.stock_quantity = max(0, plant.stock_quantity - item.quantity)
                            if plant.stock_quantity == 0:
                                plant.is_available = False
                            plant.save(update_fields=["stock_quantity", "is_available"])
                except Order.DoesNotExist:
                    pass

        return HttpResponse(status=status.HTTP_200_OK)


class SellerOrderListView(generics.ListAPIView):
    """
    GET /api/orders/seller/
    Lists orders containing items sold by the logged-in seller.
    """
    serializer_class = OrderSerializer
    permission_classes = [IsSeller]

    def get_queryset(self):
        seller_profile = self.request.user.seller_profile
        return (
            Order.objects.filter(items__plant__seller=seller_profile)
            .distinct()
            .prefetch_related("items__plant")
            .order_by("-created_at")
        )


class SellerUpdateOrderStatusView(APIView):
    """
    PATCH /api/orders/seller/<int:order_id>/status/
    Allows sellers to update delivery progression (e.g. PAID -> SHIPPED -> DELIVERED).
    """
    permission_classes = [IsSeller]

    def patch(self, request, order_id):
        order = get_object_or_404(
            Order,
            pk=order_id,
            items__plant__seller=request.user.seller_profile
        )

        new_status = request.data.get("status")
        valid_transitions = [
            Order.OrderStatus.SHIPPED,
            Order.OrderStatus.DELIVERED,
            Order.OrderStatus.CANCELLED,
        ]

        if new_status not in valid_transitions:
            return Response(
                {"error": f"Invalid status update. Choose from: {valid_transitions}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        order.status = new_status
        order.save(update_fields=["status"])

        return Response({
            "status": "Order status updated successfully",
            "new_status": order.status,
        })