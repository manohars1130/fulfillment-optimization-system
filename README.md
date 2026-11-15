# Fulfillment Node Selection and Delivery Promise System

## Project Overview

A Django-based fulfillment management system designed to select appropriate warehouses, allocate inventory, generate shipments, calculate delivery promises, track shipment events, and detect operational exceptions.

The system demonstrates a complete order-to-delivery workflow using Python, Django, Django REST Framework, MySQL, and synthetic operational data.

## Business Problem

E-commerce businesses must decide which warehouse should fulfill an order while considering:

- Available warehouse inventory
- Daily warehouse processing capacity
- Customer delivery zones
- Carrier service availability
- Carrier cutoff times
- Delivery transit times
- Split shipments
- Shipment tracking
- Delivery delays and exceptions

Incorrect fulfillment decisions can cause delayed deliveries, stock inconsistencies, and inaccurate customer promises.

## Proposed Solution

The system applies rule-based fulfillment decisions, maintains shipment and tracking information, and generates validation reports.

### Business Workflow

1. Create products, warehouses, carriers, and inventory records.
2. Create customer orders and order lines.
3. Evaluate warehouse inventory and capacity.
4. Allocate inventory across eligible warehouses.
5. Generate shipments from successful allocations.
6. Select compatible carrier services.
7. Calculate dispatch dates and delivery promises.
8. Record shipment tracking events.
9. Derive order delivery status.
10. Validate operational consistency and identify anomalies.

Orders without sufficient inventory or warehouse capacity are classified as allocation exceptions.

## Technology Stack

| Component | Technology |
|---|---|
| Programming language | Python |
| Backend | Django |
| REST APIs | Django REST Framework |
| Database | MySQL |
| Frontend | HTML, CSS, Bootstrap, JavaScript |
| Data generation | Python, CSV |
| Automated testing | Django Test Framework |
| Version control | Git and GitHub |

## Core Entities

The solution includes the following business entities:

1. Order
2. OrderLine
3. SKU
4. FulfillmentNode
5. Inventory
6. WarehouseCapacity
7. Carrier
8. ServiceLevel
9. Shipment
10. TrackingEvent
11. DeliveryPromise

Supporting entities include Allocation, ShipmentLine, CarrierZone, CarrierCalendar, and OrderStatusEvent.

## Synthetic Dataset

The full-scale dataset was generated using the reproducible seed `20261022`.

| Entity / Metric | Count |
|---|---:|
| Orders | 50,000 |
| Fulfillment warehouses | 20 |
| Carriers | 10 |
| Shipments | 24,234 |
| Tracking events | 100,000 |
| Successfully allocated orders | 23,886 |
| Allocation exceptions | 26,114 |

All data is synthetic and does not contain real customer information.

## Business Rules

### Inventory Allocation

- Allocations cannot exceed available warehouse inventory.
- Daily warehouse capacity must be respected.
- An order may be allocated across multiple warehouses.
- If the complete order cannot be allocated, planned reservations are rolled back.
- Allocation exceptions are explicitly recorded.

### Carrier Selection

- Carrier services must support the destination zone.
- Carrier cutoff times influence planned dispatch.
- Transit days determine the expected delivery date.
- Invalid services and unsupported destinations must be rejected.

### Shipment Tracking

The main tracking workflow is:

`DISPATCHED → IN_TRANSIT → OUT_FOR_DELIVERY → DELIVERED`

The synthetic full dataset also includes an `ARRIVED_AT_HUB` tracking event.

### Delivery Promises

Delivery promises are calculated from eligible carrier services, dispatch scheduling, and transit-day rules.

### Split Shipments

An order may generate multiple shipments.

The order-level delivery status must be consistent with the statuses of its shipments.

## Ground-Truth Anomalies

Five deliberately introduced anomaly categories are used to evaluate business-rule validation.

| Anomaly | Description |
|---|---|
| PROMISE_BEFORE_ORDER | Delivery promise precedes order |
| ALLOCATION_EXCEEDS_STOCK | Allocation exceeds available physical stock |
| UNSUPPORTED_CARRIER_ZONE | Shipping service does not support destination |
| DELIVERED_BEFORE_DISPATCH | Delivery timestamp precedes dispatch |
| SPLIT_STATUS_ROLLUP_MISMATCH | Order status is inconsistent with split shipments |

The original baseline dataset remains separate from the anomaly dataset.

## Validation Results

Full-scale baseline validation:

- Detected issues: 0

Full-scale anomaly evaluation:

| Metric | Result |
|---|---:|
| Ground-truth anomalies | 5 |
| Correctly detected | 5 |
| Missed anomalies | 0 |
| Additional findings | 1 |
| Precision | 83.33% |
| Recall | 100.00% |
| F1-score | 90.91% |

The additional validation finding was an order-line over-allocation caused by an intentionally oversized warehouse allocation.

These metrics evaluate the five labelled anomaly scenarios and should not be interpreted as accuracy on all possible real-world anomalies.

## Installation and Setup

### 1. Clone Repository

```bash
git clone YOUR_REPOSITORY_URL
cd fulfillment_system
```

### 2. Create Virtual Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 4. Configure MySQL

Create a MySQL database and configure its connection using the project's environment settings.

Do not commit actual database passwords or private credentials.

### 5. Apply Migrations

```powershell
python manage.py migrate
```

### 6. Create Administrator

```powershell
python manage.py createsuperuser
```

### 7. Start Application

```powershell
python manage.py runserver
```

Open:

- Dashboard: http://127.0.0.1:8000/
- Django Admin: http://127.0.0.1:8000/admin/
- Orders API: http://127.0.0.1:8000/api/orders/

## Generate Synthetic Data

Execute these scripts from the project root.

### Generate Master and Transaction Data

```powershell
python scripts/generate_data.py --scale full --seed 20261022
```

### Simulate Warehouse Allocation

```powershell
python scripts/simulate_allocations.py --scale full
```

### Generate Shipping and Tracking Records

```powershell
python scripts/simulate_shipping.py --scale full --seed 20261022
```

### Complete the Tracking Event Target

```powershell
python scripts/complete_tracking_events.py --scale full
```

### Validate Baseline Data

```powershell
python scripts/validate_data.py --scale full
```

### Inject Labelled Anomalies

```powershell
python scripts/inject_anomalies.py --scale full
```

### Validate Anomaly Dataset

```powershell
python scripts/validate_data.py --scale full_anomalies
```

### Evaluate Anomaly Detection

```powershell
python scripts/evaluate_accuracy.py --scale full_anomalies
```

Generated CSV files and reports are saved under `data/full/` and `data/full_anomalies/`.

**Note:** The CSV simulation pipeline is separate from the Django application's MySQL database. Generating CSV files does not automatically import them into MySQL.

## Automated Testing

Run Django system checks:

```powershell
python manage.py check
```

Run the complete automated test suite:

```powershell
python manage.py test -v 2
```

The latest executed Django test suite completed successfully.

## Limitations

- The synthetic simulator models business scenarios rather than live fulfillment operations.
- Full carrier holiday-calendar coverage must be verified separately.
- Allocation exception rates depend on the synthetic inventory and capacity inputs.
- The reported anomaly metrics are based on controlled injected scenarios.
- Production deployment would require additional security, monitoring, concurrency, and performance testing.

## Future Improvements

- Carrier holiday-aware delivery scheduling
- Warehouse optimization using cost and geographic distance
- Real-time carrier integrations
- Inventory replenishment planning
- Predictive delivery-delay estimation
- Expanded exception and anomaly evaluation

## Conclusion

This project demonstrates fulfillment-node selection, inventory and capacity management, carrier eligibility, delivery-promise calculation, shipment tracking, exception handling, reproducible synthetic data generation, and automated validation.

The solution is designed to expose operational decisions, preserve workflow relationships, and provide measurable evaluation results.
