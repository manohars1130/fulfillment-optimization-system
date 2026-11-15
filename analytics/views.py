
from django.db.models import Count, Sum, F
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser


from orders.models import Order
from fulfillment.models import (
    Inventory,
    FulfillmentNode,
    Allocation,
)
from shipping.models import Shipment, TrackingEvent
from shipping.validation import validate_order_shipping


class DashboardSummaryAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        # Order metrics
        total_orders = Order.objects.count()

        pending_orders = Order.objects.filter(
            status="PENDING"
        ).count()

        allocated_orders = Order.objects.filter(
            status="ALLOCATED"
        ).count()

        delivered_orders = Order.objects.filter(
            status="DELIVERED"
        ).count()

        exception_orders = Order.objects.filter(
            status="EXCEPTION"
        ).count()

        # Shipping metrics
        total_shipments = Shipment.objects.count()

        delivered_shipments = Shipment.objects.filter(
            status="DELIVERED"
        ).count()

        total_tracking_events = TrackingEvent.objects.count()

        # Allocation metrics
        allocated_units = (
            Allocation.objects.aggregate(
                total=Sum("quantity")
            )["total"] or 0
        )

        # Inventory metrics
        stock = Inventory.objects.aggregate(
            on_hand=Sum("on_hand"),
            reserved=Sum("reserved")
        )

        on_hand = stock["on_hand"] or 0
        reserved = stock["reserved"] or 0

        # Warehouse summary
        warehouses = list(
            FulfillmentNode.objects.annotate(
                stock=Sum("inventory__on_hand"),
                reserved_stock=Sum("inventory__reserved")
            ).values(
                "node_id",
                "name",
                "city",
                "stock",
                "reserved_stock",
            ).order_by("node_id")
        )

        for warehouse in warehouses:
            warehouse["stock"] = warehouse["stock"] or 0
            warehouse["reserved_stock"] = (
                warehouse["reserved_stock"] or 0
            )
            warehouse["available_stock"] = (
                warehouse["stock"]
                - warehouse["reserved_stock"]
            )

        # Delivery rate based on shipment status
        delivery_rate = (
            round(
                (delivered_shipments / total_shipments) * 100,
                2
            )
            if total_shipments else 0
        )

        return Response({
            "total_orders": total_orders,
            "pending_orders": pending_orders,
            "allocated_orders": allocated_orders,
            "delivered_orders": delivered_orders,
            "exception_orders": exception_orders,
            "total_shipments": total_shipments,
            "delivered_shipments": delivered_shipments,
            "total_tracking_events": total_tracking_events,
            "allocated_units": allocated_units,
            "on_hand": on_hand,
            "reserved_stock": reserved,
            "available_stock": on_hand - reserved,
            "delivery_completion_rate": delivery_rate,
            "warehouses": warehouses,
        })


class ValidationReportAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        # Small, bounded preview for the frontend.
        # Full-dataset validation will use a management command.
        orders = Order.objects.filter(
            shipments__isnull=False
        ).distinct().order_by("order_id")[:20]

        issues = []

        for order in orders:
            issues.extend(validate_order_shipping(order))

        return Response({
            "orders_checked": len(orders),
            "issues_count": len(issues),
            "issues": issues,
            "scope": "first_20_orders_with_shipments",
        })



# Create your views here.
