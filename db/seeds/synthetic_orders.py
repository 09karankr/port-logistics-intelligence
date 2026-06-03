"""
Synthetic order seeder.

Creates realistic purchase orders linked to both real AIS vessels and
simulated vessels so the Shipments tab is always populated.

Usage:
    python db/seeds/synthetic_orders.py
"""

import os
import random
import uuid
from datetime import datetime, timedelta, timezone

import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]

CUSTOMERS = [
    "Walmart Global Imports", "Target Merchandise LLC", "Amazon.com Inc.",
    "Home Depot Supply Chain", "Best Buy Electronics", "Nike APAC Logistics",
    "Apple Inc. (Component Div.)", "IKEA Supply AG", "Costco Wholesale Corp",
    "Dollar General Sourcing", "Ford Motor Parts", "Tesla Battery Div.",
    "Samsung Electronics", "LG International", "Unilever Supply Chain",
    "Procter & Gamble", "3M Global Logistics", "Caterpillar Inc.",
    "John Deere International", "Pfizer Global Supply",
]

COMMODITIES = [
    "Consumer Electronics", "Automotive Parts", "Apparel & Textiles",
    "Furniture & Home Goods", "Industrial Machinery", "Pharmaceutical Goods",
    "Food & Beverage", "Chemicals (Non-Hazardous)", "Steel Products",
    "Plastic Components", "Semiconductor Equipment", "Solar Panels",
    "Lithium Batteries", "Agricultural Products", "Rubber & Plastics",
    "Paper & Pulp", "Medical Devices", "Heavy Equipment", "Frozen Goods",
]

LANE_PAIRS = [
    ("CNSHA", "USLAX"),
    ("CNSHA", "USLGB"),
    ("SGSIN", "NLRTM"),
    ("CNNGB", "USLAX"),
    ("KRPUS", "USLGB"),
    ("AEJEA", "NLRTM"),
    ("CNSHA", "DEHAM"),
    ("CNSZX", "USLAX"),
    ("CNTAO", "NLRTM"),
    ("HKHKG", "USLGB"),
    ("SGSIN", "BEANR"),
    ("CNSHA", "SGSIN"),
    ("KRPUS", "NLRTM"),
    ("AEJEA", "DEHAM"),
]


def seed(n_orders: int = 200):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # Collect all available vessel MMSIs (real + simulated)
    cur.execute("""
        SELECT DISTINCT mmsi FROM vessels
        ORDER BY mmsi
        LIMIT 500
    """)
    all_mmsis = [r[0] for r in cur.fetchall()]

    if not all_mmsis:
        print("No vessels found. Start the AIS consumer and simulator first.")
        conn.close()
        return

    # Port locode → id map
    cur.execute("SELECT id, un_locode FROM ports WHERE un_locode IS NOT NULL")
    port_map = {row[1]: row[0] for row in cur.fetchall()}

    if not port_map:
        print("No ports found — run the port seed first.")
        conn.close()
        return

    now = datetime.now(tz=timezone.utc)
    rng = random.Random(42)  # deterministic so re-runs don't duplicate content
    inserted = 0

    for i in range(n_orders):
        origin_locode, dest_locode = rng.choice(LANE_PAIRS)
        origin_id = port_map.get(origin_locode)
        dest_id   = port_map.get(dest_locode)
        if not origin_id or not dest_id:
            continue

        mmsi      = rng.choice(all_mmsis)
        customer  = rng.choice(CUSTOMERS)
        commodity = rng.choice(COMMODITIES)
        value_usd = rng.randint(500_000, 200_000_000) * 100

        etd_offset   = rng.randint(3, 45)
        transit_days = rng.randint(14, 50)
        scheduled_etd = now - timedelta(days=etd_offset)
        scheduled_eta = scheduled_etd + timedelta(days=transit_days)

        # Some orders are already late (for risk demo)
        if rng.random() < 0.3:
            scheduled_eta = now - timedelta(days=rng.randint(1, 10))

        order_ref = f"PO-{now.year}-{i:04d}-{str(uuid.uuid4())[:6].upper()}"

        cur.execute(
            """
            INSERT INTO shipment_orders
                (id, order_ref, customer, commodity, value_usd,
                 origin_port, dest_port, vessel_mmsi,
                 scheduled_etd, scheduled_eta, actual_etd, status)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'in_transit')
            ON CONFLICT (order_ref) DO NOTHING
            """,
            (
                str(uuid.uuid4()), order_ref, customer, commodity, value_usd,
                origin_id, dest_id, mmsi,
                scheduled_etd, scheduled_eta, scheduled_etd,
            ),
        )
        inserted += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"Seeded {inserted} orders across {len(all_mmsis)} vessels.")


if __name__ == "__main__":
    seed()
