from django.test import TestCase

from catalog.models import SKU
from fulfillment.models import (
    FulfillmentNode,
    Inventory
)


class InventoryTests(TestCase):

    def setUp(self):
        self.sku = SKU.objects.create(
            sku_id="SKU-000001",
            name="Smartphone",
            category="Electronics",
            unit_weight_kg="0.250"
        )

        self.node = FulfillmentNode.objects.create(
            node_id="FUL-2026-000001",
            name="Hyderabad Warehouse",
            city="Hyderabad",
            state="Telangana"
        )

    def test_available_stock(self):
        inventory = Inventory.objects.create(
            node=self.node,
            sku=self.sku,
            on_hand=100,
            reserved=30
        )

        self.assertEqual(
            inventory.available,
            70
        )

    def test_zero_available_stock(self):
        inventory = Inventory.objects.create(
            node=self.node,
            sku=self.sku,
            on_hand=50,
            reserved=50
        )

        self.assertEqual(
            inventory.available,
            0
        )

from datetime import datetime
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.utils import timezone

from catalog.models import SKU
from orders.models import Order, OrderLine

from fulfillment.models import (
    FulfillmentNode,
    Inventory,
    WarehouseCapacity,
    Allocation,
    OrderStatusEvent,
)

from fulfillment.services import (
    allocate_order,
    AllocationError,
)


class AllocationEngineTests(TestCase):

    def setUp(self):
        self.sku = SKU.objects.create(
            sku_id="SKU-000001",
            name="Smartphone",
            category="Electronics",
            unit_weight_kg="0.250"
        )

        self.order = Order.objects.create(
            order_id="ORD-2026-000001",
            customer_name="Test Customer",
            destination_city="Hyderabad",
            destination_zone="HYD",
            order_time=datetime(
                2026, 11, 15, 10, 0,
                tzinfo=ZoneInfo("Asia/Kolkata")
            )
        )

        self.line = OrderLine.objects.create(
            order=self.order,
            sku=self.sku,
            quantity=8
        )

        self.hyd = FulfillmentNode.objects.create(
            node_id="FUL-2026-000001",
            name="Hyderabad Warehouse",
            city="Hyderabad",
            state="Telangana"
        )

        self.blr = FulfillmentNode.objects.create(
            node_id="FUL-2026-000002",
            name="Bengaluru Warehouse",
            city="Bengaluru",
            state="Karnataka"
        )

        Inventory.objects.create(
            node=self.hyd,
            sku=self.sku,
            on_hand=5,
            reserved=0
        )

        Inventory.objects.create(
            node=self.blr,
            sku=self.sku,
            on_hand=10,
            reserved=0
        )

        for node in [self.hyd, self.blr]:
            WarehouseCapacity.objects.create(
                node=node,
                capacity_date=timezone.localdate(),
                daily_limit=20,
                reserved_slots=0
            )

    def test_split_allocation(self):
        result = allocate_order(self.order.order_id)

        self.assertEqual(result["status"], "ALLOCATED")
        self.assertEqual(len(result["allocations"]), 2)

        self.assertEqual(
            sum(a["quantity"] for a in result["allocations"]),
            8
        )

        hyd_stock = Inventory.objects.get(
            node=self.hyd,
            sku=self.sku
        )

        blr_stock = Inventory.objects.get(
            node=self.blr,
            sku=self.sku
        )

        self.assertEqual(hyd_stock.reserved, 5)
        self.assertEqual(blr_stock.reserved, 3)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "ALLOCATED")

        self.assertTrue(
            OrderStatusEvent.objects.filter(
                order=self.order,
                new_status="ALLOCATED"
            ).exists()
        )

    def test_insufficient_stock_rolls_back(self):
        Inventory.objects.filter(
            node=self.blr,
            sku=self.sku
        ).update(on_hand=1)

        with self.assertRaises(AllocationError):
            allocate_order(self.order.order_id)

        self.assertEqual(
            Allocation.objects.filter(
                order_line__order=self.order
            ).count(),
            0
        )

        self.assertEqual(
            Inventory.objects.get(
                node=self.hyd,
                sku=self.sku
            ).reserved,
            0
        )

        self.assertEqual(
            WarehouseCapacity.objects.get(
                node=self.hyd
            ).reserved_slots,
            0
        )

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "PENDING")

    def test_capacity_limit(self):
        WarehouseCapacity.objects.filter(
            node=self.hyd
        ).update(
            daily_limit=2,
            reserved_slots=0
        )

        result = allocate_order(self.order.order_id)

        allocations = result["allocations"]

        self.assertEqual(allocations[0]["quantity"], 2)
        self.assertEqual(allocations[1]["quantity"], 6)

    def test_duplicate_allocation_rejected(self):
        allocate_order(self.order.order_id)

        with self.assertRaises(AllocationError):
            allocate_order(self.order.order_id)

        self.assertEqual(
            Allocation.objects.filter(
                order_line__order=self.order
            ).count(),
            2
        )