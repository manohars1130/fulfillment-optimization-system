
import argparse
import csv
from datetime import datetime
from pathlib import Path


TARGET = 100000


def complete_tracking_events(scale):
    folder = Path("data") / scale
    path = folder / "tracking_events.csv"

    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        events = list(reader)

    if not fieldnames:
        raise ValueError("Tracking CSV has no header")

    if len(events) > TARGET:
        raise ValueError(
            f"Already have {len(events)} events, "
            f"which exceeds target {TARGET}"
        )

    needed = TARGET - len(events)

    if needed == 0:
        print("Tracking events already complete:", TARGET)
        return

    by_shipment = {}

    for event in events:
        by_shipment.setdefault(
            event["shipment_id"], {}
        )[event["event_type"]] = event

    existing_ids = {
        event["event_id"] for event in events
    }

    additional = []

    for shipment_id in sorted(by_shipment):
        if len(additional) >= needed:
            break

        shipment_events = by_shipment[shipment_id]

        dispatched = shipment_events.get("DISPATCHED")
        in_transit = shipment_events.get("IN_TRANSIT")
        out_for_delivery = shipment_events.get(
            "OUT_FOR_DELIVERY"
        )

        if not all((
            dispatched,
            in_transit,
            out_for_delivery
        )):
            continue

        start = datetime.fromisoformat(
            in_transit["event_time"]
        )
        end = datetime.fromisoformat(
            out_for_delivery["event_time"]
        )

        if end <= start:
            continue

        # Place new event strictly between existing events.
        hub_time = start + (end - start) / 2

        event_id = f"TRK-{shipment_id}-005"

        if event_id in existing_ids:
            continue

        additional.append({
            "event_id": event_id,
            "shipment_id": shipment_id,
            "event_type": "ARRIVED_AT_HUB",
            "event_time": hub_time.isoformat(),
        })

    if len(additional) != needed:
        raise ValueError(
            f"Need {needed} events, but only "
            f"{len(additional)} eligible shipments found"
        )

    events.extend(additional)

    # Preserve chronological sequence within shipments.
    events.sort(
        key=lambda event: (
            event["shipment_id"],
            event["event_time"],
            event["event_id"]
        )
    )

    # The current validator sorts event_id rather
    # than event_time. It must be updated separately.
    with path.open(
        "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.DictWriter(
            f, fieldnames=fieldnames
        )
        writer.writeheader()
        writer.writerows(events)

    print("Additional events:", len(additional))
    print("Total tracking events:", len(events))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scale",
        choices=["full"],
        default="full"
    )

    args = parser.parse_args()
    complete_tracking_events(args.scale)
