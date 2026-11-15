from datetime import datetime,timedelta,time
from zoneinfo import ZoneInfo
from django.utils import timezone
from shipping.validation import validate_order_shipping
from catalog.models import SKU
from orders.models import Order, OrderLine
from django.test import TestCase
from django.core.exceptions import ValidationError
from fulfillment.services import allocate_order
from shipping.promise_engine import calculate_promise

from shipping.shipment_service import (
    create_order_shipments,
    ShipmentCreationError,
)

from fulfillment.models import (
    FulfillmentNode,
    Inventory,
    WarehouseCapacity,
)

from shipping.models import (

    CarrierCalendar,
    Shipment,
    DeliveryPromise,
    TrackingEvent,
)
from shipping.tracking_service import (
    record_tracking_event,
    TrackingValidationError,
)
from shipping.models import (
    Carrier,
    ServiceLevel,
    CarrierZone,
)

from shipping.services import (
    get_eligible_services,
    validate_carrier_service,
)

class CarrierServiceTests(TestCase):

    def setUp(self):

        self.carrier = Carrier.objects.create(
            carrier_id="CAR-2026-000001",
            name="Carrier A"
        )

        self.service = ServiceLevel.objects.create(
            service_id="SRV-2026-000001",
            carrier=self.carrier,
            name="Express",
            transit_days=2,
            cutoff_time=time(16, 0)
        )

        CarrierZone.objects.create(
            service=self.service,
            destination_zone="HYD",
            is_supported=True
        )

    def test_supported_zone(self):
        service = validate_carrier_service(
            self.service.service_id,
            "HYD"
        )

        self.assertEqual(
            service.service_id,
            self.service.service_id
        )

    def test_unsupported_zone(self):
        with self.assertRaises(ValidationError):
            validate_carrier_service(
                self.service.service_id,
                "DEL"
            )

    def test_eligible_services(self):
        services = get_eligible_services("HYD")

        self.assertEqual(services.count(), 1)

    def test_inactive_carrier(self):
        self.carrier.is_active = False
        self.carrier.save()

        services = get_eligible_services("HYD")

        self.assertEqual(services.count(), 0)



class DeliveryPromiseTests(TestCase):

    def setUp(self):
        self.carrier = Carrier.objects.create(
            carrier_id="CAR-2026-000001",
            name="Carrier A"
        )

        self.service = ServiceLevel.objects.create(
            service_id="SRV-2026-000001",
            carrier=self.carrier,
            name="Express",
            transit_days=2,
            cutoff_time=time(16, 0),
        )

    def test_cutoff_and_weekend(self):
        # Friday, November 13, 2026 at 5 PM IST.
        order_time = datetime(
            2026, 11, 13, 17, 0,
            tzinfo=ZoneInfo("Asia/Kolkata")
        )

        result = calculate_promise(
            self.service, order_time
        )

        self.assertEqual(
            str(result["dispatch_date"]), "2026-11-16"
        )
        self.assertEqual(
            str(result["delivery_date"]), "2026-11-18"
        )

    def test_carrier_holiday(self):
        CarrierCalendar.objects.create(
            carrier=self.carrier,
            calendar_date="2026-11-16",
            is_working_day=False,
            reason="Test holiday",
        )

        order_time = datetime(
            2026, 11, 13, 17, 0,
            tzinfo=ZoneInfo("Asia/Kolkata")
        )

        result = calculate_promise(
            self.service, order_time
        )

        self.assertEqual(
            str(result["dispatch_date"]), "2026-11-17"
        )
        self.assertEqual(
            str(result["delivery_date"]), "2026-11-19"
        )


class ShipmentWorkflowTests(TestCase):

    def setUp(self):
        self.order_time = datetime(
            2026, 11, 13, 15, 0,
            tzinfo=ZoneInfo("Asia/Kolkata")
        )

        self.sku = SKU.objects.create(
            sku_id="SKU-000001",
            name="Smartphone",
            category="Electronics",
            unit_weight_kg="0.250",
        )

        self.order = Order.objects.create(
            order_id="ORD-2026-000001",
            customer_name="Test Customer",
            destination_city="Hyderabad",
            destination_zone="HYD",
            order_time=self.order_time,
        )

        OrderLine.objects.create(
            order=self.order,
            sku=self.sku,
            quantity=3,
        )

        self.node = FulfillmentNode.objects.create(
            node_id="FUL-2026-000001",
            name="Hyderabad Warehouse",
            city="Hyderabad",
            state="Telangana",
        )

        Inventory.objects.create(
            node=self.node,
            sku=self.sku,
            on_hand=10,
            reserved=0,
        )

        WarehouseCapacity.objects.create(
            node=self.node,
            capacity_date=timezone.localdate(),
            daily_limit=100,
            reserved_slots=0,
        )

        self.carrier = Carrier.objects.create(
            carrier_id="CAR-2026-000001",
            name="Carrier A",
        )

        self.service = ServiceLevel.objects.create(
            service_id="SRV-2026-000001",
            carrier=self.carrier,
            name="Express",
            transit_days=2,
            cutoff_time=time(16, 0),
        )

        CarrierZone.objects.create(
            service=self.service,
            destination_zone="HYD",
            is_supported=True,
        )

        allocate_order(self.order.order_id)

    def create_shipment(self):
        create_order_shipments(
            self.order.order_id,
            reference_time=self.order_time,
        )

        return Shipment.objects.get(order=self.order)

    def test_shipment_creation_and_promise(self):
        shipment = self.create_shipment()

        self.assertEqual(
            shipment.lines.count(), 1
        )

        self.assertEqual(
            shipment.lines.first().quantity, 3
        )

        promise = DeliveryPromise.objects.get(
            order=self.order
        )

        self.assertEqual(
            promise.promised_date,
            shipment.expected_delivery_date
        )

        # Reload the latest order status from MySQL.
        self.order.refresh_from_db()

        self.assertEqual(
            validate_order_shipping(self.order),
            []
        )
    def test_duplicate_shipment_rejected(self):
        self.create_shipment()

        with self.assertRaises(ShipmentCreationError):
            create_order_shipments(
                self.order.order_id,
                reference_time=self.order_time,
            )

        self.assertEqual(
            Shipment.objects.filter(
                order=self.order
            ).count(),
            1
        )

    def test_delivered_before_dispatch_rejected(self):
        shipment = self.create_shipment()

        with self.assertRaises(TrackingValidationError):
            record_tracking_event(
                shipment.shipment_id,
                "DELIVERED",
            )

        self.assertEqual(
            TrackingEvent.objects.filter(
                shipment=shipment
            ).count(),
            0
        )

    def test_complete_delivery_workflow(self):
        shipment = self.create_shipment()

        timestamps = [
            datetime(2026, 11, 13, 15, 30,
                     tzinfo=ZoneInfo("Asia/Kolkata")),
            datetime(2026, 11, 16, 10, 0,
                     tzinfo=ZoneInfo("Asia/Kolkata")),
            datetime(2026, 11, 17, 9, 0,
                     tzinfo=ZoneInfo("Asia/Kolkata")),
            datetime(2026, 11, 18, 13, 0,
                     tzinfo=ZoneInfo("Asia/Kolkata")),
        ]

        events = [
            "DISPATCHED",
            "IN_TRANSIT",
            "OUT_FOR_DELIVERY",
            "DELIVERED",
        ]

        for event_type, timestamp in zip(events, timestamps):
            record_tracking_event(
                shipment.shipment_id,
                event_type,
                event_time=timestamp,
            )

        shipment.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(
            shipment.status, "DELIVERED"
        )
        self.assertEqual(
            self.order.status, "DELIVERED"
        )
        self.assertEqual(
            shipment.tracking_events.count(), 4
        )
        self.assertEqual(
            validate_order_shipping(self.order), []
        )

    def test_unsupported_zone_rejects_shipment(self):
        CarrierZone.objects.filter(
            service=self.service
        ).update(is_supported=False)

        with self.assertRaises(ShipmentCreationError):
            create_order_shipments(
                self.order.order_id,
                reference_time=self.order_time,
            )

        self.assertFalse(
            Shipment.objects.filter(
                order=self.order
            ).exists()
        )
