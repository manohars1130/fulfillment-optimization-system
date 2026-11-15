
from django.db import transaction
from django.utils import timezone

from orders.models import Order
from fulfillment.models import Allocation
from shipping.models import (
    Shipment,
    ShipmentLine,
    ShipmentCounter,
    DeliveryPromise,
)
from shipping.services import get_eligible_services
from shipping.promise_engine import calculate_promise


class ShipmentCreationError(Exception):
    pass


def generate_shipment_id():
    """
    Must be called inside a database transaction.
    Uses a locked counter row for sequential IDs.
    """

    counter, _ = ShipmentCounter.objects.get_or_create(
        name="shipment",
        defaults={"next_value": 1}
    )

    counter = (
        ShipmentCounter.objects
        .select_for_update()
        .get(pk=counter.pk)
    )

    number = counter.next_value
    counter.next_value += 1
    counter.save(update_fields=["next_value"])

    return f"SHP-2026-{number:06d}"


@transaction.atomic
def create_order_shipments(order_id, reference_time=None):
    """
    Convert existing allocations into shipments.
    Entire operation succeeds or rolls back.
    """

    try:
        order = (
            Order.objects
            .select_for_update()
            .get(pk=order_id)
        )
    except Order.DoesNotExist:
        raise ShipmentCreationError("Order not found")

    if order.status != "ALLOCATED":
        raise ShipmentCreationError(
            "Order must be ALLOCATED before shipment creation"
        )

    if order.shipments.exists():
        raise ShipmentCreationError(
            "Shipments already exist for this order"
        )

    allocations = list(
        Allocation.objects.filter(
            order_line__order=order
        ).select_related(
            "order_line",
            "node"
        ).order_by("node_id", "allocation_id")
    )

    if not allocations:
        raise ShipmentCreationError(
            "No warehouse allocations found"
        )

    # Ensure every ordered quantity is accounted for.
    allocated_by_line = {}

    for allocation in allocations:
        line_id = allocation.order_line_id

        allocated_by_line[line_id] = (
            allocated_by_line.get(line_id, 0)
            + allocation.quantity
        )

    for line in order.lines.all():
        if allocated_by_line.get(line.pk, 0) != line.quantity:
            raise ShipmentCreationError(
                f"Allocation reconciliation failed: "
                f"line {line.pk}"
            )

    # Group allocated products by fulfillment node.
    grouped = {}

    for allocation in allocations:
        grouped.setdefault(
            allocation.node_id, []
        ).append(allocation)

    # Reference time allows deterministic simulation.
    planning_time = reference_time or timezone.now()

    if timezone.is_naive(planning_time):
        raise ShipmentCreationError(
            "Reference time must be timezone-aware"
        )

    # Cannot plan fulfillment before the order exists.
    planning_time = max(planning_time, order.order_time)

    shipment_results = []
    expected_dates = []

    for node_id, node_allocations in sorted(grouped.items()):

        eligible_services = list(
            get_eligible_services(
                order.destination_zone
            )
        )

        if not eligible_services:
            raise ShipmentCreationError(
                "No supported carrier service for "
                f"destination zone {order.destination_zone}"
            )

        options = []

        for service in eligible_services:
            promise = calculate_promise(
                service,
                planning_time
            )

            options.append((
                promise["delivery_date"],
                promise["dispatch_date"],
                service.service_id,
                service,
            ))

        # Earliest delivery promise wins.
        options.sort(key=lambda item: item[:3])

        delivery_date, dispatch_date, _, service = options[0]

        shipment = Shipment.objects.create(
            shipment_id=generate_shipment_id(),
            order=order,
            node_id=node_id,
            service=service,
            planned_dispatch_date=dispatch_date,
            expected_delivery_date=delivery_date,
            status="CREATED",
        )

        for allocation in node_allocations:
            ShipmentLine.objects.create(
                shipment=shipment,
                allocation=allocation,
                quantity=allocation.quantity,
            )

        shipment_results.append({
            "shipment_id": shipment.shipment_id,
            "node_id": node_id,
            "carrier": service.carrier.name,
            "service": service.name,
            "dispatch_date": str(dispatch_date),
            "delivery_date": str(delivery_date),
        })

        expected_dates.append(delivery_date)

    if not expected_dates:
        raise ShipmentCreationError(
            "No delivery dates calculated"
        )

    # Promise the date by which ALL shipments arrive.
    order_promise_date = max(expected_dates)

    DeliveryPromise.objects.create(
        promise_id=f"PROM-{order.order_id}-01",
        order=order,
        version=1,
        promised_date=order_promise_date,
        calculated_at=planning_time,
        reason="Initial fulfillment and carrier selection",
    )

    return {
        "order_id": order.order_id,
        "promise_date": str(order_promise_date),
        "shipments": shipment_results,
    }
