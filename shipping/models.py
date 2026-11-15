
from django.db import models
from django.db.models import Q


class Carrier(models.Model):
    carrier_id = models.CharField(
        max_length=30,
        primary_key=True
    )

    name = models.CharField(max_length=150)

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "carrier"

    def __str__(self):
        return self.name


class ServiceLevel(models.Model):
    service_id = models.CharField(
        max_length=30,
        primary_key=True
    )

    carrier = models.ForeignKey(
        Carrier,
        on_delete=models.PROTECT,
        related_name="service_levels"
    )

    name = models.CharField(max_length=100)

    transit_days = models.PositiveIntegerField()

    cutoff_time = models.TimeField()

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "service_level"

    def __str__(self):

        return f"{self.carrier.name} - {self.name}"

class CarrierZone(models.Model):
    service = models.ForeignKey(
        ServiceLevel,
        on_delete=models.PROTECT,
        related_name="zones"
    )

    destination_zone = models.CharField(
        max_length=30
    )

    is_supported = models.BooleanField(default=True)

    class Meta:
        db_table = "carrier_zone"

        constraints = [
            models.UniqueConstraint(
                fields=["service", "destination_zone"],
                name="unique_service_destination_zone"
            )
        ]


class CarrierCalendar(models.Model):
    carrier = models.ForeignKey(
        Carrier,
        on_delete=models.PROTECT,
        related_name="calendar"
    )

    calendar_date = models.DateField()

    is_working_day = models.BooleanField(default=True)

    reason = models.CharField(
        max_length=150,
        blank=True
    )

    class Meta:
        db_table = "carrier_calendar"

        constraints = [
            models.UniqueConstraint(
                fields=["carrier", "calendar_date"],
                name="unique_carrier_calendar_date"
            )
        ]



class ShipmentCounter(models.Model):
    name = models.CharField(max_length=30, primary_key=True)
    next_value = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "shipment_counter"


class Shipment(models.Model):

    STATUS_CHOICES = [
        ("CREATED", "Created"),
        ("DISPATCHED", "Dispatched"),
        ("IN_TRANSIT", "In Transit"),
        ("OUT_FOR_DELIVERY", "Out for Delivery"),
        ("DELIVERED", "Delivered"),
        ("EXCEPTION", "Exception"),
    ]

    shipment_id = models.CharField(
        max_length=30,
        primary_key=True
    )

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="shipments"
    )

    node = models.ForeignKey(
        "fulfillment.FulfillmentNode",
        on_delete=models.PROTECT,
        related_name="shipments"
    )

    service = models.ForeignKey(
        "shipping.ServiceLevel",
        on_delete=models.PROTECT,
        related_name="shipments"
    )

    planned_dispatch_date = models.DateField()
    expected_delivery_date = models.DateField()

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="CREATED"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "shipment"

        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    expected_delivery_date__gte=models.F(
                        "planned_dispatch_date"
                    )
                ),
                name="shipment_delivery_after_dispatch"
            ),
        ]

    def __str__(self):
        return self.shipment_id


class ShipmentLine(models.Model):
    shipment_line_id = models.BigAutoField(primary_key=True)

    shipment = models.ForeignKey(
        Shipment,
        on_delete=models.PROTECT,
        related_name="lines"
    )

    allocation = models.OneToOneField(
        "fulfillment.Allocation",
        on_delete=models.PROTECT,
        related_name="shipment_line"
    )

    quantity = models.PositiveIntegerField()

    class Meta:
        db_table = "shipment_line"

        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="shipment_line_quantity_positive"
            )
        ]


class TrackingEvent(models.Model):

    EVENT_CHOICES = [
        ("DISPATCHED", "Dispatched"),
        ("IN_TRANSIT", "In Transit"),
        ("OUT_FOR_DELIVERY", "Out for Delivery"),
        ("DELIVERED", "Delivered"),
        ("EXCEPTION", "Exception"),
    ]

    event_id = models.CharField(
        max_length=50,
        primary_key=True
    )

    shipment = models.ForeignKey(
        Shipment,
        on_delete=models.PROTECT,
        related_name="tracking_events"
    )

    event_type = models.CharField(
        max_length=30,
        choices=EVENT_CHOICES
    )

    event_time = models.DateTimeField()

    remarks = models.CharField(
        max_length=255,
        blank=True
    )

    class Meta:
        db_table = "tracking_event"
        ordering = ["event_time", "event_id"]

    def __str__(self):
        return self.event_id


class DeliveryPromise(models.Model):

    promise_id = models.CharField(
        max_length=50,
        primary_key=True
    )

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="delivery_promises"
    )

    version = models.PositiveIntegerField(default=1)

    promised_date = models.DateField()
    calculated_at = models.DateTimeField()

    reason = models.CharField(
        max_length=255,
        default="Initial shipping promise"
    )

    class Meta:
        db_table = "delivery_promise"

        constraints = [
            models.UniqueConstraint(
                fields=["order", "version"],
                name="unique_order_promise_version"
            )
        ]

    def __str__(self):
        return self.promise_id
