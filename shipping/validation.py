
from shipping.models import Shipment, DeliveryPromise
from shipping.services import validate_carrier_service
from shipping.tracking_service import derive_order_status
from django.core.exceptions import ValidationError

from django.utils import timezone
def validate_order_shipping(order):
    issues = []

    shipments = list(
        Shipment.objects.filter(order=order)
        .prefetch_related(
            "lines__allocation",
            "tracking_events"
        )
    )

    # Check shipment quantities.
    for shipment in shipments:
        for line in shipment.lines.all():
            if line.quantity != line.allocation.quantity:
                issues.append({
                    "issue_type": "SHIPMENT_QUANTITY_MISMATCH",
                    "shipment_id": shipment.shipment_id,
                })

        # Validate carrier service zone.
        try:
            validate_carrier_service(
                shipment.service_id,
                order.destination_zone
            )
        except ValidationError:
            issues.append({
                "issue_type": "UNSUPPORTED_CARRIER_ZONE",
                "shipment_id": shipment.shipment_id,
            })

        # Validate event chronology and dispatch ordering.
        events = sorted(
            shipment.tracking_events.all(),
            key=lambda e: (e.event_time, e.event_id)
        )

        dispatch_events = [
            e for e in events
            if e.event_type == "DISPATCHED"
        ]

        delivery_events = [
            e for e in events
            if e.event_type == "DELIVERED"
        ]

        if delivery_events and (
            not dispatch_events
            or delivery_events[0].event_time
            < dispatch_events[0].event_time
        ):
            issues.append({
                "issue_type": "DELIVERED_BEFORE_DISPATCH",
                "shipment_id": shipment.shipment_id,
            })

        if (
            events
            and shipment.status != events[-1].event_type
        ):
            issues.append({
                "issue_type": "SHIPMENT_STATUS_MISMATCH",
                "shipment_id": shipment.shipment_id,
            })

    # Validate overall order status.
    expected_status = derive_order_status(order)

    if expected_status != order.status:
        issues.append({
            "issue_type": "ORDER_STATUS_MISMATCH",
            "order_id": order.order_id,
        })

    # Validate latest order delivery promise.
    promise = DeliveryPromise.objects.filter(
        order=order
    ).order_by("-version").first()

    if promise:

        local_order_date = timezone.localtime(
            order.order_time,
            timezone.get_default_timezone()
        ).date()

        if promise.promised_date < local_order_date:
            issues.append({
                "issue_type": "PROMISE_BEFORE_ORDER",
                "order_id": order.order_id,
            })

        if shipments and (
                promise.promised_date
                < max(s.expected_delivery_date for s in shipments)
        ):
            issues.append({
                "issue_type": "PROMISE_TOO_EARLY",
                "order_id": order.order_id,
            })

    return issues
