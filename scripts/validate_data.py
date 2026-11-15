
import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, date
from pathlib import Path


def load_csv(folder, filename):
    path = folder / filename

    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def validate(scale):
    folder = Path("data") / scale

    datasets = {
        "orders": load_csv(folder, "orders.csv"),
        "order_lines": load_csv(folder, "order_lines.csv"),
        "skus": load_csv(folder, "skus.csv"),
        "nodes": load_csv(folder, "fulfillment_nodes.csv"),
        "inventory": load_csv(folder, "inventory.csv"),
        "allocations": load_csv(folder, "allocations.csv"),
        "capacities": load_csv(folder, "capacity_balances.csv"),
        "shipments": load_csv(folder, "shipments.csv"),
        "shipment_lines": load_csv(folder, "shipment_lines.csv"),
        "tracking": load_csv(folder, "tracking_events.csv"),
        "promises": load_csv(folder, "delivery_promises.csv"),
        "outcomes": load_csv(folder, "order_outcomes.csv"),
    }

    issues = []

    def add_issue(issue_type, record_id, details):
        issues.append({
            "issue_type": issue_type,
            "record_id": str(record_id),
            "details": details,
        })

    def check_unique(rows, field, dataset_name):
        values = [row[field] for row in rows]
        counts = Counter(values)

        for value, count in counts.items():
            if not value or count != 1:
                add_issue(
                    "DUPLICATE_OR_MISSING_PK",
                    value,
                    f"{dataset_name}.{field}: count={count}"
                )

    # 1. Check primary keys
    primary_keys = {
        "orders": "order_id",
        "order_lines": "line_id",
        "skus": "sku_id",
        "nodes": "node_id",
        "inventory": "inventory_id",
        "allocations": "allocation_id",
        "shipments": "shipment_id",
        "tracking": "event_id",
        "promises": "promise_id",
    }

    for name, field in primary_keys.items():
        check_unique(datasets[name], field, name)

    # 2. Build parent lookups
    orders = {x["order_id"]: x for x in datasets["orders"]}
    lines = {x["line_id"]: x for x in datasets["order_lines"]}
    skus = {x["sku_id"] for x in datasets["skus"]}
    nodes = {x["node_id"] for x in datasets["nodes"]}
    shipments = {
        x["shipment_id"]: x for x in datasets["shipments"]
    }
    allocations = {
        x["allocation_id"]: x for x in datasets["allocations"]
    }

    # 3. Validate order lines
    for line in datasets["order_lines"]:
        if line["order_id"] not in orders:
            add_issue(
                "INVALID_ORDER_FK", line["line_id"],
                "Order does not exist"
            )

        if line["sku_id"] not in skus:
            add_issue(
                "INVALID_SKU_FK", line["line_id"],
                "SKU does not exist"
            )

        if int(line["quantity"]) <= 0:
            add_issue(
                "INVALID_QUANTITY", line["line_id"],
                "Quantity must be positive"
            )

    # 4. Validate inventory balances
    for row in datasets["inventory"]:
        if row["node_id"] not in nodes:
            add_issue(
                "INVALID_NODE_FK", row["inventory_id"],
                "Warehouse does not exist"
            )

        if row["sku_id"] not in skus:
            add_issue(
                "INVALID_SKU_FK", row["inventory_id"],
                "SKU does not exist"
            )

    for row in load_csv(folder, "inventory_balances.csv"):
        on_hand = int(row["on_hand"])
        reserved = int(row["reserved"])
        available = int(row["available"])

        if (
            reserved < 0
            or reserved > on_hand
            or available != on_hand - reserved
        ):
            add_issue(
                "INVENTORY_BALANCE_MISMATCH",
                f"{row['node_id']}:{row['sku_id']}",
                "Inventory arithmetic is inconsistent"
            )

    # 5. Validate warehouse capacity
    for row in datasets["capacities"]:
        limit = int(row["daily_limit"])
        reserved = int(row["reserved_slots"])
        available = int(row["available_capacity"])

        if (
            reserved < 0
            or reserved > limit
            or available != limit - reserved
        ):
            add_issue(
                "CAPACITY_EXCEEDED",
                row["node_id"],
                "Warehouse capacity exceeded or miscalculated"
            )

    # 6. Validate allocations
    allocated_by_line = defaultdict(int)

    for allocation in datasets["allocations"]:
        line_id = allocation["line_id"]
        quantity = int(allocation["quantity"])

        if line_id not in lines:
            add_issue(
                "INVALID_ALLOCATION_FK",
                allocation["allocation_id"],
                "Order line does not exist"
            )
            continue

        if allocation["node_id"] not in nodes:
            add_issue(
                "INVALID_ALLOCATION_NODE",
                allocation["allocation_id"],
                "Fulfillment node does not exist"
            )

        if quantity <= 0:
            add_issue(
                "INVALID_ALLOCATION_QUANTITY",
                allocation["allocation_id"],
                "Allocation must be positive"
            )

        if allocation["sku_id"] != lines[line_id]["sku_id"]:
            add_issue(
                "ALLOCATION_SKU_MISMATCH",
                allocation["allocation_id"],
                "Allocation SKU differs from order line"
            )

        allocated_by_line[line_id] += quantity

    for line_id, quantity in allocated_by_line.items():
        if quantity > int(lines[line_id]["quantity"]):
            add_issue(
                "OVER_ALLOCATED_ORDER_LINE",
                line_id,
                "Allocated quantity exceeds ordered quantity"
            )

    # Detect allocations exceeding warehouse stock

    # Detect individual allocations exceeding warehouse stock
    stock_lookup = {
        (row["node_id"], row["sku_id"]): int(row["on_hand"])
        for row in datasets["inventory"]
    }

    for allocation in datasets["allocations"]:
        key = (
            allocation["node_id"],
            allocation["sku_id"]
        )

        quantity = int(allocation["quantity"])
        on_hand = stock_lookup.get(key)

        if on_hand is not None and quantity > on_hand:
            add_issue(
                "ALLOCATION_EXCEEDS_STOCK",
                allocation["allocation_id"],
                "Single allocation exceeds warehouse stock"
            )

    # 7. Validate shipment references
    for shipment in datasets["shipments"]:
        shipment_id = shipment["shipment_id"]

        if shipment["order_id"] not in orders:
            add_issue(
                "INVALID_SHIPMENT_ORDER_FK",
                shipment_id,
                "Shipment references missing order"
            )

        if shipment["node_id"] not in nodes:
            add_issue(
                "INVALID_SHIPMENT_NODE_FK",
                shipment_id,
                "Shipment references missing warehouse"
            )

        if (
            shipment["expected_delivery_date"]
            < shipment["planned_dispatch_date"]
        ):
            add_issue(
                "INVALID_SHIPMENT_DATES",
                shipment_id,
                "Delivery promise precedes dispatch"
            )

    # 8. Validate shipment lines

    for row in datasets["shipment_lines"]:
        if row["shipment_id"] not in shipments:
            add_issue(
                "INVALID_SHIPMENT_LINE_FK",
                row["shipment_id"],
                "Shipment not found"
            )

        if row["allocation_id"] not in allocations:
            add_issue(
                "INVALID_SHIPMENT_ALLOCATION_FK",
                row["allocation_id"],
                "Allocation not found"
            )

    # 9. Validate carrier zones
    service_ids = {
        row["service_id"]
        for row in load_csv(folder, "service_levels.csv")
    }

    supported_zones = {
        (row["service_id"], row["destination_zone"])
        for row in load_csv(folder, "carrier_zones.csv")
        if row["is_supported"].lower() == "true"
    }

    for shipment in datasets["shipments"]:
        order = orders.get(shipment["order_id"])

        if order is None:
            continue

        if shipment["service_id"] not in service_ids:
            add_issue(
                "INVALID_SERVICE_FK",
                shipment["shipment_id"],
                "Service does not exist"
            )

        elif (
                shipment["service_id"],
                order["destination_zone"]
        ) not in supported_zones:
            add_issue(
                "UNSUPPORTED_CARRIER_ZONE",
                shipment["shipment_id"],
                "Unsupported carrier destination zone"
            )
    # 9. Validate tracking events
    tracking_by_shipment = defaultdict(list)

    for event in datasets["tracking"]:
        if event["shipment_id"] not in shipments:
            add_issue(
                "INVALID_TRACKING_FK",
                event["event_id"],
                "Shipment does not exist"
            )
            continue

        tracking_by_shipment[event["shipment_id"]].append(event)

    for shipment_id, events in tracking_by_shipment.items():
        events.sort(
            key=lambda e: (
                datetime.fromisoformat(e["event_time"]),
                e["event_id"]
            )
        )

        previous_time = None
        dispatched_at = None

        for event in events:
            timestamp = datetime.fromisoformat(
                event["event_time"]
            )

            if previous_time and timestamp < previous_time:
                add_issue(
                    "INVALID_TRACKING_SEQUENCE",
                    event["event_id"],
                    "Event timestamp precedes previous event"
                )

            if event["event_type"] == "DISPATCHED":
                dispatched_at = timestamp

            if event["event_type"] == "DELIVERED":
                if dispatched_at is None or timestamp < dispatched_at:
                    add_issue(
                        "DELIVERED_BEFORE_DISPATCH",
                        event["event_id"],
                        "Delivery occurred before dispatch"
                    )

            previous_time = timestamp

    # 10. Validate delivery promises
    for promise in datasets["promises"]:
        order_id = promise["order_id"]

        if order_id not in orders:
            add_issue(
                "INVALID_PROMISE_FK",
                promise["promise_id"],
                "Order does not exist"
            )
            continue

        order_date = datetime.fromisoformat(
            orders[order_id]["order_time"]
        ).date()

        promised_date = date.fromisoformat(
            promise["promised_date"]
        )

        if promised_date < order_date:
            add_issue(
                "PROMISE_BEFORE_ORDER",
                promise["promise_id"],
                "Promised date precedes order date"
            )

    # Validate split-shipment order status
    status_file = folder / "order_delivery_status.csv"

    if status_file.exists():
        status_rows = load_csv(
            folder,
            "order_delivery_status.csv"
        )

        shipments_by_order = defaultdict(list)

        for shipment in datasets["shipments"]:
            shipments_by_order[
                shipment["order_id"]
            ].append(shipment)

        for status_row in status_rows:
            order_id = status_row["order_id"]
            actual_status = status_row["delivery_status"]

            order_shipments = shipments_by_order.get(
                order_id, []
            )

            # Split shipment means more than one shipment.
            if len(order_shipments) <= 1:
                continue

            shipment_statuses = [
                shipment["status"]
                for shipment in order_shipments
            ]

            if all(
                status == "DELIVERED"
                for status in shipment_statuses
            ):
                expected_status = "DELIVERED"

            elif any(
                status == "DELIVERED"
                for status in shipment_statuses
            ):
                expected_status = "PARTIALLY_DELIVERED"

            else:
                expected_status = "SHIPPED"

            if actual_status != expected_status:
                add_issue(
                    "SPLIT_STATUS_ROLLUP_MISMATCH",
                    order_id,
                    (
                        f"Expected {expected_status}, "
                        f"found {actual_status}"
                    )
                )

    # 11. Export validation results
    report = {
        "scale": scale,
        "row_counts": {
            name: len(rows)
            for name, rows in datasets.items()
        },
        "issues_count": len(issues),
        "issues_by_type": dict(
            sorted(Counter(
                issue["issue_type"] for issue in issues
            ).items())
        ),
        "issues": issues,
    }

    report_path = folder / "validation_report.json"

    with report_path.open(
        "w", encoding="utf-8"
    ) as file:
        json.dump(report, file, indent=2)

    print("\nVALIDATION SUMMARY")
    print("------------------")
    print("Dataset:", scale)
    print("Total issues:", len(issues))

    for issue_type, count in report["issues_by_type"].items():
        print(f"{issue_type}: {count}")

    print("Report:", report_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--scale",
        choices=[
            "starter",
            "full",
            "starter_anomalies",
            "full_anomalies"
        ],
        default="starter"
    )

    args = parser.parse_args()
    validate(args.scale)
