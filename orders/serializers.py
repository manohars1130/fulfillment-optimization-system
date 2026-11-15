
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .models import Order, OrderLine


class OrderLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderLine
        fields = ["line_id", "sku", "quantity"]
        read_only_fields = ["line_id"]


class OrderSerializer(serializers.ModelSerializer):
    lines = OrderLineSerializer(many=True)

    class Meta:
        model = Order
        fields = [
            "order_id",
            "customer_name",
            "destination_city",
            "destination_zone",
            "order_time",
            "status",
            "lines",
        ]
        read_only_fields = [
            "order_id",
            "order_time",
            "status",
        ]

    def validate_lines(self, value):
        if not value:
            raise serializers.ValidationError(
                "At least one order line is required."
            )

        if any(line["quantity"] <= 0 for line in value):
            raise serializers.ValidationError(
                "Quantity must be greater than zero."
            )

        return value

    @transaction.atomic
    def create(self, validated_data):
        lines_data = validated_data.pop("lines")

        # A database-backed counter should eventually replace
        # this provisional ID generation for concurrent requests.
        last_id = (
            Order.objects.filter(order_id__startswith="ORD-2026-")
            .order_by("-order_id")
            .values_list("order_id", flat=True)
            .first()
        )

        next_number = int(last_id.rsplit("-", 1)[-1]) + 1 if last_id else 1
        order_id = f"ORD-2026-{next_number:06d}"

        order = Order.objects.create(
            order_id=order_id,
            order_time=timezone.now(),
            **validated_data
        )

        for line_data in lines_data:
            OrderLine.objects.create(
                order=order,
                **line_data
            )

        return order
