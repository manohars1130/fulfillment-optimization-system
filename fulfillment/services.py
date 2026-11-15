from django.db import transaction
from django.utils import timezone

from orders.models import Order
from fulfillment.models import (
    Inventory,
    WarehouseCapacity,
    Allocation,
    OrderStatusEvent,
)


class AllocationError(Exception):
    """Business exception for allocation failures."""
    pass


@transaction.atomic
def allocate_order(order_id):
    # Step 1: Lock the order.
    # Prevent two requests from allocating it simultaneously.
    try:
        order = (
            Order.objects
            .select_for_update()
            .get(order_id=order_id)
        )
    except Order.DoesNotExist:
        raise AllocationError("Order not found")

    # Step 2: Check order eligibility.
    if order.status != "PENDING":
        raise AllocationError(
            f"Order status must be PENDING, "
            f"found {order.status}"
        )

    if Allocation.objects.filter(
        order_line__order=order
    ).exists():
        raise AllocationError(
            "Order already has allocation records"
        )

    lines = list(
        order.lines.select_related("sku").order_by("line_id")
    )

    if not lines:
        raise AllocationError("Order has no order lines")

    if any(line.quantity <= 0 for line in lines):
        raise AllocationError(
            "Order lines must have positive quantities"
        )

    allocation_date = timezone.localdate()
    results = []

    # Step 3: Allocate each order line.
    for line in lines:
        remaining = line.quantity

        # Candidate warehouses in stable order.
        # A future version will rank by delivery performance.
        candidate_ids = list(
            Inventory.objects.filter(
                sku=line.sku,
                node__is_active=True
            )
            .order_by("node_id")
            .values_list("inventory_id", flat=True)
        )

        for inventory_id in candidate_ids:
            if remaining == 0:
                break

            # Step 4: Lock the inventory balance.
            inventory = (
                Inventory.objects
                .select_for_update()
                .get(pk=inventory_id)
            )

            if not inventory.node.is_active:
                continue

            stock_available = (
                inventory.on_hand - inventory.reserved
            )

            if stock_available <= 0:
                continue

            # Step 5: Lock warehouse capacity.
            try:
                capacity = (
                    WarehouseCapacity.objects
                    .select_for_update()
                    .get(
                        node_id=inventory.node_id,
                        capacity_date=allocation_date
                    )
                )
            except WarehouseCapacity.DoesNotExist:
                continue

            capacity_available = (
                capacity.daily_limit - capacity.reserved_slots
            )

            if capacity_available <= 0:
                continue

            # Step 6: Determine safe allocation.
            allocated_qty = min(
                remaining,
                stock_available,
                capacity_available
            )

            if allocated_qty <= 0:
                continue

            # Step 7: Reserve inventory.
            inventory.reserved += allocated_qty
            inventory.save(update_fields=["reserved"])

            # Step 8: Reserve capacity.
            capacity.reserved_slots += allocated_qty
            capacity.save(update_fields=["reserved_slots"])

            # Step 9: Persist allocation decision.
            allocation = Allocation.objects.create(
                order_line=line,
                node_id=inventory.node_id,
                quantity=allocated_qty,
                capacity_date=allocation_date,
            )

            results.append({
                "allocation_id": allocation.allocation_id,
                "line_id": line.line_id,
                "sku_id": line.sku_id,
                "node_id": inventory.node_id,
                "quantity": allocated_qty,
            })

            remaining -= allocated_qty

        # If any line cannot be fully allocated,
        # roll back all changes to this order.
        if remaining > 0:
            raise AllocationError(
                f"Insufficient stock or capacity "
                f"for SKU {line.sku_id}. "
                f"Unallocated quantity: {remaining}"
            )

    # Step 10: Record successful state transition.
    previous_status = order.status
    order.status = "ALLOCATED"
    order.save(update_fields=["status"])

    OrderStatusEvent.objects.create(
        order=order,
        previous_status=previous_status,
        new_status="ALLOCATED",
        reason="Inventory and warehouse capacity reserved",
    )

    return {
        "order_id": order.order_id,
        "status": "ALLOCATED",
        "allocations": results,
    }