
import argparse
import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def read_csv(folder, filename):
    with (folder / filename).open(
        newline="", encoding="utf-8"
    ) as file:
        return list(csv.DictReader(file))


def write_csv(folder, filename, rows, fields):
    with (folder / filename).open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fields
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"{filename}: {len(rows)} records")


def simulate(scale):
    folder = Path("data") / scale

    orders = read_csv(folder, "orders.csv")
    lines = read_csv(folder, "order_lines.csv")
    inventory_rows = read_csv(folder, "inventory.csv")
    capacity_rows = read_csv(
        folder, "warehouse_capacity.csv"
    )
    node_rows = read_csv(
        folder, "fulfillment_nodes.csv"
    )

    active_nodes = sorted(
        node["node_id"]
        for node in node_rows
        if str(node["is_active"]).lower() == "true"
    )

    # Inventory lookup: (node_id, sku_id)
    inventory = {}

    for row in inventory_rows:
        key = (row["node_id"], row["sku_id"])

        inventory[key] = {
            "on_hand": int(row["on_hand"]),
            "reserved": int(row["reserved"]),
        }

    # Capacity lookup: (node_id, date)
    capacities = {}

    for row in capacity_rows:
        key = (
            row["node_id"],
            row["capacity_date"]
        )

        capacities[key] = {
            "daily_limit": int(row["daily_limit"]),
            "reserved_slots": int(row["reserved_slots"]),
        }

    lines_by_order = defaultdict(list)

    for line in lines:
        lines_by_order[line["order_id"]].append(line)

    allocations = []
    outcomes = []

    allocation_number = 1

    for order_index, order in enumerate(
        sorted(orders, key=lambda x: (
            x["order_time"], x["order_id"]
        ))
    ):
        order_id = order["order_id"]

        order_date = datetime.fromisoformat(
            order["order_time"]
        ).date().isoformat()

        order_lines = lines_by_order[order_id]

        # Reserve quantities only after the
        # entire order can be fulfilled.
        pending_inventory = defaultdict(int)
        pending_capacity = defaultdict(int)
        planned_allocations = []

        valid = True
        reason = ""

        if not order_lines:
            valid = False
            reason = "NO_ORDER_LINES"

        for line in order_lines:
            if not valid:
                break

            sku_id = line["sku_id"]
            remaining = int(line["quantity"])

            if remaining <= 0:
                valid = False
                reason = "INVALID_QUANTITY"
                break

            # Rotate warehouse preference to create
            # realistic allocation variation.
            offset = order_index % len(active_nodes)

            candidates = (
                active_nodes[offset:]
                + active_nodes[:offset]
            )

            for node_id in candidates:
                if remaining == 0:
                    break

                stock_key = (node_id, sku_id)
                capacity_key = (node_id, order_date)

                stock = inventory.get(stock_key)
                capacity = capacities.get(capacity_key)

                if stock is None or capacity is None:
                    continue

                stock_available = (
                    stock["on_hand"]
                    - stock["reserved"]
                    - pending_inventory[stock_key]
                )

                capacity_available = (
                    capacity["daily_limit"]
                    - capacity["reserved_slots"]
                    - pending_capacity[capacity_key]
                )

                quantity = min(
                    remaining,
                    stock_available,
                    capacity_available
                )

                if quantity <= 0:
                    continue

                pending_inventory[stock_key] += quantity
                pending_capacity[capacity_key] += quantity

                planned_allocations.append({
                    "order_id": order_id,
                    "line_id": line["line_id"],
                    "sku_id": sku_id,
                    "node_id": node_id,
                    "quantity": quantity,
                    "allocation_date": order_date,
                })

                remaining -= quantity

            if remaining > 0:
                valid = False
                reason = "INSUFFICIENT_STOCK_OR_CAPACITY"
                break

        if valid:
            # Commit reservations after all lines succeed.
            for key, quantity in pending_inventory.items():
                inventory[key]["reserved"] += quantity

            for key, quantity in pending_capacity.items():
                capacities[key]["reserved_slots"] += quantity

            for allocation in planned_allocations:
                allocation["allocation_id"] = (
                    f"ALLOC-2026-{allocation_number:06d}"
                )
                allocation_number += 1

                allocations.append(allocation)

            status = "ALLOCATED"

        else:
            # No partial reservations are committed.
            status = "EXCEPTION"

        outcomes.append({
            "order_id": order_id,
            "status": status,
            "reason": reason,
            "allocated_quantity": (
                sum(
                    a["quantity"]
                    for a in planned_allocations
                ) if valid else 0
            ),
        })

    inventory_balances = []

    for (node_id, sku_id), balance in sorted(
        inventory.items()
    ):
        inventory_balances.append({
            "node_id": node_id,
            "sku_id": sku_id,
            "on_hand": balance["on_hand"],
            "reserved": balance["reserved"],
            "available": (
                balance["on_hand"]
                - balance["reserved"]
            ),
        })

    capacity_balances = []

    for (node_id, date), balance in sorted(
        capacities.items()
    ):
        capacity_balances.append({
            "node_id": node_id,
            "capacity_date": date,
            "daily_limit": balance["daily_limit"],
            "reserved_slots": balance["reserved_slots"],
            "available_capacity": (
                balance["daily_limit"]
                - balance["reserved_slots"]
            ),
        })

    write_csv(
        folder, "allocations.csv", allocations,
        [
            "allocation_id", "order_id", "line_id",
            "sku_id", "node_id", "quantity",
            "allocation_date"
        ]
    )

    write_csv(
        folder, "order_outcomes.csv", outcomes,
        [
            "order_id", "status", "reason",
            "allocated_quantity"
        ]
    )

    write_csv(
        folder, "inventory_balances.csv",
        inventory_balances,
        [
            "node_id", "sku_id", "on_hand",
            "reserved", "available"
        ]
    )

    write_csv(
        folder, "capacity_balances.csv",
        capacity_balances,
        [
            "node_id", "capacity_date",
            "daily_limit", "reserved_slots",
            "available_capacity"
        ]
    )

    allocated = sum(
        o["status"] == "ALLOCATED"
        for o in outcomes
    )

    print(f"\nOrders evaluated: {len(outcomes)}")
    print(f"Successfully allocated: {allocated}")
    print(f"Exceptions: {len(outcomes) - allocated}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--scale",
        choices=["starter", "full"],
        default="starter"
    )

    args = parser.parse_args()
    simulate(args.scale)
