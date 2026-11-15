
import argparse
import csv
import random
from collections import defaultdict
from datetime import datetime, timedelta, time
from pathlib import Path
from zoneinfo import ZoneInfo


IST = ZoneInfo("Asia/Kolkata")


def read_csv(folder, filename):
    with (folder / filename).open(
        newline="", encoding="utf-8"
    ) as file:
        return list(csv.DictReader(file))


def save_csv(folder, filename, rows, fields):
    with (folder / filename).open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"{filename}: {len(rows)} records")


def working_day(day):
    return day.weekday() < 5


def next_working_day(day):
    while not working_day(day):
        day += timedelta(days=1)
    return day


def calculate_dates(order_time, service):
    local_time = datetime.fromisoformat(
        order_time
    ).astimezone(IST)

    cutoff = time.fromisoformat(
        service["cutoff_time"]
    )

    dispatch = local_time.date()

    if not working_day(dispatch):
        dispatch = next_working_day(dispatch)

    elif local_time.time().replace(tzinfo=None) > cutoff:
        dispatch = next_working_day(
            dispatch + timedelta(days=1)
        )

    delivery = dispatch
    remaining = int(service["transit_days"])

    while remaining > 0:
        delivery += timedelta(days=1)

        if working_day(delivery):
            remaining -= 1

    return dispatch, delivery


def simulate_shipping(scale, seed):
    folder = Path("data") / scale
    rng = random.Random(seed + 2)

    orders = read_csv(folder, "orders.csv")
    allocations = read_csv(folder, "allocations.csv")
    services = read_csv(folder, "service_levels.csv")
    zones = read_csv(folder, "carrier_zones.csv")
    carriers = read_csv(folder, "carriers.csv")

    valid_carriers = {
        c["carrier_id"]
        for c in carriers
        if c["is_active"].lower() == "true"
    }

    supported = {
        (z["service_id"], z["destination_zone"])
        for z in zones
        if z["is_supported"].lower() == "true"
    }

    order_lookup = {
        o["order_id"]: o for o in orders
    }

    grouped = defaultdict(list)

    for allocation in allocations:
        grouped[
            (allocation["order_id"], allocation["node_id"])
        ].append(allocation)

    shipments = []
    shipment_lines = []
    tracking = []
    promises = []
    actual_outcomes = []

    shipment_number = 1

    for (order_id, node_id), node_allocations in sorted(
        grouped.items()
    ):
        order = order_lookup[order_id]

        options = []

        for service in services:
            if service["carrier_id"] not in valid_carriers:
                continue

            if service["is_active"].lower() != "true":
                continue

            if (
                service["service_id"],
                order["destination_zone"]
            ) not in supported:
                continue

            dispatch, delivery = calculate_dates(
                order["order_time"], service
            )

            options.append((
                delivery,
                dispatch,
                service["service_id"],
                service
            ))

        if not options:
            raise ValueError(
                f"No eligible service for {order_id}"
            )

        options.sort(key=lambda x: x[:3])
        delivery, dispatch, _, service = options[0]

        shipment_id = f"SHP-2026-{shipment_number:06d}"
        shipment_number += 1

        # Deterministic scenario-based carrier delay.
        delayed = rng.random() < 0.10
        delay_days = rng.choice([1, 2]) if delayed else 0

        actual_delivery = delivery

        for _ in range(delay_days):
            actual_delivery = next_working_day(
                actual_delivery + timedelta(days=1)
            )

        dispatch_time = datetime.combine(
            dispatch, time(10, 0), tzinfo=IST
        )

        actual_time = datetime.combine(
            actual_delivery, time(16, 0), tzinfo=IST
        )

        in_transit_time = dispatch_time + timedelta(
            hours=4
        )

        out_for_delivery_time = datetime.combine(
            actual_delivery, time(9, 0), tzinfo=IST
        )

        event_plan = [
            ("DISPATCHED", dispatch_time),
            ("IN_TRANSIT", in_transit_time),
            ("OUT_FOR_DELIVERY", out_for_delivery_time),
            ("DELIVERED", actual_time),
        ]

        for sequence, (event_type, timestamp) in enumerate(
            event_plan, start=1
        ):
            tracking.append({
                "event_id": (
                    f"TRK-{shipment_id}-{sequence:03d}"
                ),
                "shipment_id": shipment_id,
                "event_type": event_type,
                "event_time": timestamp.isoformat(),
            })

        shipments.append({
            "shipment_id": shipment_id,
            "order_id": order_id,
            "node_id": node_id,
            "service_id": service["service_id"],
            "planned_dispatch_date": dispatch,
            "expected_delivery_date": delivery,
            "status": "DELIVERED",
        })

        for allocation in node_allocations:
            shipment_lines.append({
                "shipment_id": shipment_id,
                "allocation_id": allocation["allocation_id"],
                "quantity": allocation["quantity"],
            })

        actual_outcomes.append({
            "shipment_id": shipment_id,
            "actual_delivery_date": actual_delivery,
            "is_late": actual_delivery > delivery,
            "delay_days": delay_days,
        })

    shipments_by_order = defaultdict(list)

    for shipment in shipments:
        shipments_by_order[shipment["order_id"]].append(
            shipment
        )

    for order_id, order_shipments in sorted(
        shipments_by_order.items()
    ):
        promised_date = max(
            s["expected_delivery_date"]
            for s in order_shipments
        )

        promises.append({
            "promise_id": f"PROM-{order_id}-01",
            "order_id": order_id,
            "version": 1,
            "promised_date": promised_date,
            "reason": "Calculated from eligible shipment services",
        })

    save_csv(
        folder, "shipments.csv", shipments,
        [
            "shipment_id", "order_id", "node_id",
            "service_id", "planned_dispatch_date",
            "expected_delivery_date", "status"
        ]
    )

    save_csv(
        folder, "shipment_lines.csv", shipment_lines,
        ["shipment_id", "allocation_id", "quantity"]
    )

    save_csv(
        folder, "tracking_events.csv", tracking,
        [
            "event_id", "shipment_id",
            "event_type", "event_time"
        ]
    )

    save_csv(
        folder, "delivery_promises.csv", promises,
        [
            "promise_id", "order_id", "version",
            "promised_date", "reason"
        ]
    )

    save_csv(
        folder, "delivery_outcomes.csv", actual_outcomes,
        [
            "shipment_id", "actual_delivery_date",
            "is_late", "delay_days"
        ]
    )

    print("\nShipping simulation completed.")
    print("All data is synthetic.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--scale",
        choices=["starter", "full"],
        default="starter"
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=20261022
    )

    args = parser.parse_args()
    simulate_shipping(args.scale, args.seed)
