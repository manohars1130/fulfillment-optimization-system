
import argparse
import csv
import json
import shutil
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path


def read_csv(folder, filename):
    with (folder / filename).open(
        newline="", encoding="utf-8"
    ) as f:
        return list(csv.DictReader(f))


def write_csv(folder, filename, rows):
    if not rows:
        raise ValueError(f"No rows in {filename}")

    with (folder / filename).open(
        "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.DictWriter(
            f, fieldnames=list(rows[0].keys())
        )
        writer.writeheader()
        writer.writerows(rows)


def inject(scale):
    source = Path("data") / scale
    target = Path("data") / f"{scale}_anomalies"

    if not source.exists():
        raise FileNotFoundError(source)

    # Copy original data; never modify the baseline.
    if target.exists():
        shutil.rmtree(target)

    shutil.copytree(source, target)

    orders = read_csv(target, "orders.csv")
    allocations = read_csv(target, "allocations.csv")
    inventory = read_csv(target, "inventory.csv")
    shipments = read_csv(target, "shipments.csv")
    tracking = read_csv(target, "tracking_events.csv")
    promises = read_csv(target, "delivery_promises.csv")
    services = read_csv(target, "service_levels.csv")
    carriers = read_csv(target, "carriers.csv")

    order_lookup = {o["order_id"]: o for o in orders}
    shipment_lookup = {
        s["shipment_id"]: s for s in shipments
    }

    # Find an actual split order.
    shipment_counts = Counter(
        s["order_id"] for s in shipments
    )
    split_orders = sorted(
        oid for oid, count in shipment_counts.items()
        if count > 1
    )

    if not split_orders:
        raise ValueError(
            "No split shipments in baseline. "
            "Generate split coverage before injecting "
            "the split-status anomaly."
        )

    ground_truth = []

    def label(issue_type, record_id, details):
        ground_truth.append({
            "issue_type": issue_type,
            "record_id": record_id,
            "expected_label": 1,
            "details": details
        })

    # 1. Promise before order time
    promise = promises[0]
    order = order_lookup[promise["order_id"]]

    order_time = datetime.fromisoformat(
        order["order_time"]
    )

    promise["promised_date"] = (
        order_time.date() - timedelta(days=1)
    ).isoformat()

    label(
        "PROMISE_BEFORE_ORDER",
        promise["promise_id"],
        "Promised date earlier than order date"
    )

    # 2. Allocation exceeds warehouse stock
    allocation = allocations[0]

    matching_inventory = next(
        inv for inv in inventory
        if inv["node_id"] == allocation["node_id"]
        and inv["sku_id"] == allocation["sku_id"]
    )

    allocation["quantity"] = (
        str(int(matching_inventory["on_hand"]) + 1)
    )

    label(
        "ALLOCATION_EXCEEDS_STOCK",
        allocation["allocation_id"],
        "Allocated quantity exceeds physical stock"
    )

    # 3. Carrier service unsupported for destination
    # Add a valid service FK, but do not provide zone support.
    shipment = shipments[0]

    new_service_id = "SRV-2026-UNSUPPORTED"

    if any(s["service_id"] == new_service_id for s in services):
        raise ValueError("Reserved test service ID already exists")

    template = services[0].copy()
    template["service_id"] = new_service_id
    template["carrier_id"] = carriers[0]["carrier_id"]
    template["is_active"] = "True"

    services.append(template)
    shipment["service_id"] = new_service_id

    label(
        "UNSUPPORTED_CARRIER_ZONE",
        shipment["shipment_id"],
        "Service has no supported destination-zone mapping"
    )

    # 4. Shipment delivered before dispatch
    # Choose a different shipment when possible.
    delivered_events = [
        e for e in tracking
        if e["event_type"] == "DELIVERED"
        and e["shipment_id"] != shipment["shipment_id"]
    ]

    if not delivered_events:
        raise ValueError("No suitable delivery tracking event")

    event = delivered_events[0]
    related_events = [
        e for e in tracking
        if e["shipment_id"] == event["shipment_id"]
    ]

    dispatch_event = next(
        e for e in related_events
        if e["event_type"] == "DISPATCHED"
    )

    dispatch_time = datetime.fromisoformat(
        dispatch_event["event_time"]
    )

    event["event_time"] = (
        dispatch_time - timedelta(hours=1)
    ).isoformat()

    label(
        "DELIVERED_BEFORE_DISPATCH",
        event["event_id"],
        "Delivery timestamp precedes dispatch"
    )

    # 5. Incorrect split-shipment rollup
    # Generate a status snapshot from shipment statuses.
    status_rows = []

    for order_id in sorted(shipment_counts):
        related = [
            s for s in shipments
            if s["order_id"] == order_id
        ]

        statuses = [s["status"] for s in related]

        if all(s == "DELIVERED" for s in statuses):
            correct_status = "DELIVERED"
        elif any(s == "DELIVERED" for s in statuses):
            correct_status = "PARTIALLY_DELIVERED"
        else:
            correct_status = "SHIPPED"

        status_rows.append({
            "order_id": order_id,
            "delivery_status": correct_status
        })

    split_order_id = split_orders[0]

    split_row = next(
        r for r in status_rows
        if r["order_id"] == split_order_id
    )

    split_row["delivery_status"] = "PARTIALLY_DELIVERED"

    label(
        "SPLIT_STATUS_ROLLUP_MISMATCH",
        split_order_id,
        "All split shipments delivered but order marked partial"
    )

    # Save labelled anomaly dataset
    write_csv(target, "allocations.csv", allocations)
    write_csv(target, "service_levels.csv", services)
    write_csv(target, "shipments.csv", shipments)
    write_csv(target, "tracking_events.csv", tracking)
    write_csv(target, "delivery_promises.csv", promises)
    write_csv(target, "order_delivery_status.csv", status_rows)
    write_csv(target, "ground_truth.csv", ground_truth)

    with (target / "ground_truth.json").open(
        "w", encoding="utf-8"
    ) as f:
        json.dump(ground_truth, f, indent=2)

    print("Anomaly injection completed")
    print("Labels:", len(ground_truth))
    print("Output:", target)

    for item in ground_truth:
        print(item["issue_type"], item["record_id"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scale",
        choices=["starter", "full"],
        default="starter"
    )
    args = parser.parse_args()
    inject(args.scale)
