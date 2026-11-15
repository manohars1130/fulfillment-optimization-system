
from django.db import transaction
from django.utils import timezone

from orders.models import Order
from fulfillment.models import OrderStatusEvent
from shipping.models import Shipment, TrackingEvent


class TrackingValidationError(Exception):
    pass


ALLOWED_TRANSITIONS = {
    "CREATED": {"DISPATCHED", "EXCEPTION"},
    "DISPATCHED": {"IN_TRANSIT", "EXCEPTION"},
    "IN_TRANSIT": {"OUT_FOR_DELIVERY", "EXCEPTION"},
    "OUT_FOR_DELIVERY": {"DELIVERED", "EXCEPTION"},
    "EXCEPTION": {"IN_TRANSIT"},
    "DELIVERED": set(),
}


def derive_order_status(order):
    """
    Calculate the order-level status from ALL shipments.
    """

    statuses = list(
        order.shipments.values_list("status", flat=True)
    )

    if not statuses:
        return order.status

    if all(s == "DELIVERED" for s in statuses):
        return "DELIVERED"

    if any(s == "DELIVERED" for s in statuses):
        return "PARTIALLY_DELIVERED"

    if all(s == "CREATED" for s in statuses):
        return "ALLOCATED"

    if any(s == "CREATED" for s in statuses):
        return "PARTIALLY_SHIPPED"

    if all(s == "EXCEPTION" for s in statuses):
        return "EXCEPTION"

    return "SHIPPED"


@transaction.atomic
def record_tracking_event(
    shipment_id,
    event_type,
    event_time=None,
    remarks=""
):
    """
    Append a tracking event and update current statuses.
    """

    try:
        shipment_reference = Shipment.objects.get(
            pk=shipment_id
        )
    except Shipment.DoesNotExist:
        raise TrackingValidationError(
            "Shipment does not exist"
        )

    order = (
        Order.objects
        .select_for_update()
        .get(pk=shipment_reference.order_id)
    )

    shipment = (
        Shipment.objects
        .select_for_update()
        .get(pk=shipment_id)
    )

    allowed = ALLOWED_TRANSITIONS.get(
        shipment.status, set()
    )

    if event_type not in allowed:
        raise TrackingValidationError(
            f"Invalid transition: "
            f"{shipment.status} -> {event_type}"
        )

    event_time = (
        event_time if event_time is not None
        else timezone.now()
    )

    if timezone.is_naive(event_time):
        raise TrackingValidationError(
            "Tracking timestamp must be timezone-aware"
        )

    if event_time < order.order_time:
        raise TrackingValidationError(
            "Tracking event precedes the order"
        )

    events = list(
        shipment.tracking_events.order_by(
            "event_time", "event_id"
        )
    )

    if events and event_time < events[-1].event_time:
        raise TrackingValidationError(
            "Tracking event is earlier than previous event"
        )

    local_date = timezone.localtime(
        event_time,
        timezone.get_default_timezone()
    ).date()

    if event_type == "DISPATCHED":
        if local_date < shipment.planned_dispatch_date:
            raise TrackingValidationError(
                "Dispatch precedes planned dispatch date"
            )

    if event_type == "DELIVERED":
        has_dispatch = shipment.tracking_events.filter(
            event_type="DISPATCHED"
        ).exists()

        if not has_dispatch:
            raise TrackingValidationError(
                "Cannot deliver before dispatch"
            )

    sequence = len(events) + 1

    tracking = TrackingEvent.objects.create(
        event_id=(
            f"TRK-{shipment.shipment_id}-{sequence:03d}"
        ),
        shipment=shipment,
        event_type=event_type,
        event_time=event_time,
        remarks=remarks,
    )

    shipment.status = event_type
    shipment.save(update_fields=["status"])

    updated_status = derive_order_status(order)

    if updated_status != order.status:
        previous_status = order.status
        order.status = updated_status
        order.save(update_fields=["status"])

        OrderStatusEvent.objects.create(
            order=order,
            previous_status=previous_status,
            new_status=updated_status,
            reason=f"Shipment tracking event: {event_type}",
        )

    return {
        "event_id": tracking.event_id,
        "shipment_id": shipment.shipment_id,
        "shipment_status": shipment.status,
        "order_status": order.status,
    }
