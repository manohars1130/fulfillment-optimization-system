
import argparse
import csv
import random
from pathlib import Path


CITIES = [
    ("Hyderabad", "Telangana"),
    ("Bengaluru", "Karnataka"),
    ("Mumbai", "Maharashtra"),
    ("Delhi", "Delhi"),
    ("Chennai", "Tamil Nadu"),
    ("Pune", "Maharashtra"),
    ("Kolkata", "West Bengal"),
    ("Ahmedabad", "Gujarat"),
    ("Jaipur", "Rajasthan"),
    ("Lucknow", "Uttar Pradesh"),
]


def save_csv(folder, filename, rows):
    path = folder / filename

    if not rows:
        raise ValueError(f"No records for {filename}")

    with path.open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(
            file, fieldnames=list(rows[0].keys())
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"{filename}: {len(rows)} records")


def generate_master_data(scale, seed):
    rng = random.Random(seed)

    output = Path("data") / scale
    output.mkdir(parents=True, exist_ok=True)

    if scale == "starter":
        node_count = 2
        carrier_count = 2
        sku_count = 10
    else:
        node_count = 20
        carrier_count = 10
        sku_count = 500

    # Generate fulfillment nodes
    nodes = []

    for i in range(1, node_count + 1):
        city, state = CITIES[(i - 1) % len(CITIES)]

        nodes.append({
            "node_id": f"FUL-2026-{i:06d}",
            "name": f"{city} Warehouse {i}",
            "city": city,
            "state": state,
            "is_active": True,
        })

    # Generate carriers
    carriers = []

    for i in range(1, carrier_count + 1):
        carriers.append({
            "carrier_id": f"CAR-2026-{i:06d}",
            "name": f"Synthetic Carrier {i}",
            "is_active": True,
        })

    # Generate SKUs
    categories = [
        "Electronics",
        "Clothing",
        "Books",
        "Accessories",
        "Home",
    ]

    skus = []

    for i in range(1, sku_count + 1):
        skus.append({
            "sku_id": f"SKU-{i:06d}",
            "name": f"Product {i}",
            "category": rng.choice(categories),
            "unit_weight_kg": f"{rng.uniform(0.1, 5):.3f}",
            "is_active": True,
        })

    save_csv(output, "fulfillment_nodes.csv", nodes)
    save_csv(output, "carriers.csv", carriers)
    save_csv(output, "skus.csv", skus)

    print(f"\nGeneration completed with seed {seed}")
    print(f"Output directory: {output.resolve()}")


from datetime import datetime, timedelta, timezone


def generate_transactions(scale, seed):
    rng = random.Random(seed + 1)

    output = Path("data") / scale

    node_count = 2 if scale == "starter" else 20
    carrier_count = 2 if scale == "starter" else 10
    sku_count = 10 if scale == "starter" else 500
    order_count = 100 if scale == "starter" else 50000

    start_date = datetime(2026, 11, 15, tzinfo=timezone.utc)

    inventories = []
    capacities = []
    services = []
    zones = []
    orders = []
    order_lines = []

    # 1. Inventory for every warehouse and SKU
    for node_num in range(1, node_count + 1):
        node_id = f"FUL-2026-{node_num:06d}"

        for sku_num in range(1, sku_count + 1):
            inventories.append({
                "inventory_id": len(inventories) + 1,
                "node_id": node_id,
                "sku_id": f"SKU-{sku_num:06d}",
                "on_hand": rng.randint(20, 500),
                "reserved": 0,
            })

        # 2. Warehouse capacity for 30 days
        for day in range(30):
            capacity_date = (
                start_date + timedelta(days=day)
            ).date()

            capacities.append({
                "capacity_id": len(capacities) + 1,
                "node_id": node_id,
                "capacity_date": capacity_date,
                "daily_limit": rng.randint(200, 500),
                "reserved_slots": 0,
            })

    destination_zones = [
        "HYD", "BLR", "MUM", "DEL"
    ]

    # 3. Carrier services and supported zones
    for carrier_num in range(1, carrier_count + 1):
        carrier_id = f"CAR-2026-{carrier_num:06d}"

        for level_num, name in enumerate(
            ["Express", "Standard"], start=1
        ):
            service_id = (
                f"SRV-2026-{carrier_num:03d}-{level_num:03d}"
            )

            services.append({
                "service_id": service_id,
                "carrier_id": carrier_id,
                "name": name,
                "transit_days": 2 if name == "Express" else 4,
                "cutoff_time": "16:00:00",
                "is_active": True,
            })

            for zone in destination_zones:
                zones.append({
                    "service_id": service_id,
                    "destination_zone": zone,
                    "is_supported": True,
                })

    # 4. Orders and dependent order lines
    for i in range(1, order_count + 1):
        order_id = f"ORD-2026-{i:06d}"

        order_time = start_date + timedelta(
            days=rng.randint(0, 20),
            hours=rng.randint(0, 23),
            minutes=rng.randint(0, 59),
        )

        orders.append({
            "order_id": order_id,
            "customer_name": f"Synthetic Customer {i}",
            "destination_city": rng.choice(
                ["Hyderabad", "Bengaluru", "Mumbai", "Delhi"]
            ),
            "destination_zone": "",
            "order_time": order_time.isoformat(),
            "status": "PENDING",
        })

        city_to_zone = {
            "Hyderabad": "HYD",
            "Bengaluru": "BLR",
            "Mumbai": "MUM",
            "Delhi": "DEL",
        }

        orders[-1]["destination_zone"] = city_to_zone[
            orders[-1]["destination_city"]
        ]

        line_count = rng.randint(1, 3)

        selected_skus = rng.sample(
            range(1, sku_count + 1),
            line_count
        )

        for sku_num in selected_skus:
            order_lines.append({
                "line_id": len(order_lines) + 1,
                "order_id": order_id,
                "sku_id": f"SKU-{sku_num:06d}",
                "quantity": rng.randint(1, 5),
            })

    # 5. Export dependent datasets
    save_csv(output, "inventory.csv", inventories)
    save_csv(output, "warehouse_capacity.csv", capacities)
    save_csv(output, "service_levels.csv", services)
    save_csv(output, "carrier_zones.csv", zones)
    save_csv(output, "orders.csv", orders)
    save_csv(output, "order_lines.csv", order_lines)

    print("Dependent data generated successfully")


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

    generate_master_data(args.scale, args.seed)
    generate_transactions(args.scale, args.seed)
