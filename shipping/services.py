from django.core.exceptions import ValidationError

from shipping.models import ServiceLevel, CarrierZone


def get_eligible_services(destination_zone):
    """
    Return active shipping services that explicitly
    support the customer's destination zone.
    """

    return ServiceLevel.objects.filter(
        is_active=True,
        carrier__is_active=True,
        zones__destination_zone=destination_zone,
        zones__is_supported=True,
    ).select_related(
        "carrier"
    ).distinct().order_by(
        "transit_days",
        "service_id"
    )


def validate_carrier_service(service_id, destination_zone):
    """
    Validate whether a shipping service can deliver
    to the selected destination.
    """

    try:
        service = ServiceLevel.objects.select_related(
            "carrier"
        ).get(service_id=service_id)

    except ServiceLevel.DoesNotExist:
        raise ValidationError("Shipping service not found")

    if not service.is_active:
        raise ValidationError("Shipping service is inactive")

    if not service.carrier.is_active:
        raise ValidationError("Carrier is inactive")

    zone_supported = CarrierZone.objects.filter(
        service=service,
        destination_zone=destination_zone,
        is_supported=True
    ).exists()

    if not zone_supported:
        raise ValidationError(
            f"Service {service_id} does not support "
            f"zone {destination_zone}"
        )

    return service