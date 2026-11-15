from django.db import models
from django.db.models import Q, F

from catalog.models import SKU


class WarehouseCapacity(models.Model):
    capacity_id = models.BigAutoField(primary_key=True)

    node = models.ForeignKey(
        "fulfillment.FulfillmentNode",
        on_delete=models.PROTECT,
        related_name="capacities"
    )

    capacity_date = models.DateField()

    daily_limit = models.PositiveIntegerField()

    reserved_slots = models.PositiveIntegerField(
        default=0
    )

    @property
    def available_capacity(self):
        return self.daily_limit - self.reserved_slots

    class Meta:
        db_table = "warehouse_capacity"

        constraints = [
            models.UniqueConstraint(
                fields=["node", "capacity_date"],
                name="unique_node_capacity_date"
            ),
            models.CheckConstraint(
                condition=Q(reserved_slots__lte=F("daily_limit")),
                name="reserved_slots_within_limit"
            ),
        ]

    def __str__(self):
        return f"{self.node.name} - {self.capacity_date}"
class FulfillmentNode(models.Model):
    node_id = models.CharField(
        max_length=30,
        primary_key=True
    )

    name = models.CharField(max_length=150)

    city = models.CharField(max_length=100)

    state = models.CharField(max_length=100)

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "fulfillment_node"

    def __str__(self):
        return self.name

class Inventory(models.Model):
    inventory_id = models.BigAutoField(
        primary_key=True
    )

    node = models.ForeignKey(
        FulfillmentNode,
        on_delete=models.PROTECT,
        related_name="inventory"
    )

    sku = models.ForeignKey(
        SKU,
        on_delete=models.PROTECT,
        related_name="inventory"
    )

    on_hand = models.PositiveIntegerField(
        default=0
    )

    reserved = models.PositiveIntegerField(
        default=0
    )

    @property
    def available(self):
        return self.on_hand - self.reserved

    class Meta:
        db_table = "inventory"

        constraints = [
            models.UniqueConstraint(
                fields=["node", "sku"],
                name="unique_node_sku"
            ),
            models.CheckConstraint(
                condition=Q(reserved__lte=F("on_hand")),
                name="reserved_not_exceed_stock"
            ),
        ]
    def __str__(self):
        return f"{self.node.name} - {self.sku.name}"


class Allocation(models.Model):
    allocation_id = models.BigAutoField(
        primary_key=True
    )

    order_line = models.ForeignKey(
        "orders.OrderLine",
        on_delete=models.PROTECT,
        related_name="allocations"
    )

    node = models.ForeignKey(
        "fulfillment.FulfillmentNode",
        on_delete=models.PROTECT,
        related_name="allocations"
    )

    quantity = models.PositiveIntegerField()

    allocated_at = models.DateTimeField(
        auto_now_add=True
    )

    capacity_date = models.DateField()

    class Meta:
        db_table = "fulfillment_allocation"

        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="allocation_quantity_positive"
            ),
        ]

    def __str__(self):
        return (
            f"{self.order_line.order_id} "
            f"- {self.node.name} "
            f"- {self.quantity}"
        )


class OrderStatusEvent(models.Model):
    event_id = models.BigAutoField(primary_key=True)

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="status_events"
    )

    previous_status = models.CharField(max_length=30)
    new_status = models.CharField(max_length=30)
    reason = models.CharField(max_length=255)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "order_status_event"
        ordering = ["occurred_at", "event_id"]