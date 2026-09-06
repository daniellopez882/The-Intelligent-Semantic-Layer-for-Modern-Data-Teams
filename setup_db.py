"""
Build the sample e-commerce database.

Two changes. The data is generated from a seed, so two runs produce the same
database and tests can assert on it. And the two ``print`` lines that
announced completion with emoji are gone: on a Windows console with a cp1252
code page they raised ``UnicodeEncodeError`` and the script failed *after*
writing the file.
"""

from __future__ import annotations

import logging
import os
import random
import sqlite3
from datetime import datetime, timedelta

logger = logging.getLogger("sql_agent.setup_db")

SEGMENTS = ["Corporate", "Retail", "Wholesale", "Affiliate"]
COUNTRIES = ["USA", "UK", "Germany", "Canada", "France", "Japan", "Australia", "Brazil"]
FIRST_NAMES = ["James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis"]
STATUSES = ["Delivered", "Shipped", "Processing", "Cancelled"]

PRODUCTS = [
    (1, "Quantum Laptop Pro", "Electronics", "Computing", 1499.99),
    (2, "Neural Mouse", "Electronics", "Peripherals", 89.00),
    (3, "ErgoDesk 3000", "Furniture", "Office", 599.99),
    (4, "Crystal Display 4K", "Electronics", "Computing", 649.99),
    (5, "Haptic Keyboard", "Electronics", "Peripherals", 129.50),
    (6, "Aero-Mesh Chair", "Furniture", "Office", 349.00),
    (7, "SmartBrew Elite", "Appliances", "Kitchen", 199.99),
    (8, "Sonic Buds V2", "Electronics", "Audio", 159.00),
    (9, "Titan Smartphone", "Electronics", "Mobile", 999.00),
    (10, "Zen Tablet 12", "Electronics", "Mobile", 499.00),
    (11, "Gourmet Grinder", "Appliances", "Kitchen", 59.99),
    (12, "Studio Monitor Pro", "Electronics", "Audio", 299.00),
]

CUSTOMER_COUNT = 40
ORDER_COUNT = 250

SCHEMA = [
    """CREATE TABLE customers (
        customer_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE,
        segment TEXT,
        country TEXT,
        signup_date DATE
    )""",
    """CREATE TABLE products (
        product_id INTEGER PRIMARY KEY,
        product_name TEXT NOT NULL,
        category TEXT,
        sub_category TEXT,
        base_price DECIMAL(10, 2)
    )""",
    """CREATE TABLE orders (
        order_id INTEGER PRIMARY KEY,
        customer_id INTEGER,
        product_id INTEGER,
        order_date DATE,
        quantity INTEGER,
        unit_price DECIMAL(10, 2),
        total_amount DECIMAL(10, 2),
        shipping_status TEXT,
        FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
        FOREIGN KEY (product_id) REFERENCES products(product_id)
    )""",
]


def create_sample_database(
    db_path: str = "ecommerce.db",
    *,
    seed: int = 42,
    now: datetime | None = None,
) -> str:
    """Create (or replace) the sample database at ``db_path``. Returns the path."""
    rng = random.Random(seed)  # noqa: S311 - sample data, not cryptography
    now = now or datetime.now()

    if os.path.exists(db_path):
        os.remove(db_path)

    customers = []
    for i in range(1, CUSTOMER_COUNT + 1):
        name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
        customers.append(
            (
                i,
                name,
                f"{name.lower().replace(' ', '.')}.{i}@demo.io",
                rng.choice(SEGMENTS),
                rng.choice(COUNTRIES),
                (now - timedelta(days=rng.randint(200, 700))).strftime("%Y-%m-%d"),
            )
        )

    orders = []
    for i in range(1, ORDER_COUNT + 1):
        product = rng.choice(PRODUCTS)
        quantity = rng.randint(1, 5)
        unit_price = round(product[4] * rng.uniform(0.9, 1.1), 2)
        orders.append(
            (
                i,
                rng.randint(1, CUSTOMER_COUNT),
                product[0],
                (now - timedelta(days=rng.randint(0, 180))).strftime("%Y-%m-%d"),
                quantity,
                unit_price,
                round(unit_price * quantity, 2),
                rng.choice(STATUSES),
            )
        )

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        for statement in SCHEMA:
            cursor.execute(statement)
        cursor.executemany("INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?)", customers)
        cursor.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?)", PRODUCTS)
        cursor.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?)", orders)
        conn.commit()
    finally:
        conn.close()

    logger.info(
        "sample database written to %s: %d customers, %d products, %d orders",
        db_path,
        CUSTOMER_COUNT,
        len(PRODUCTS),
        ORDER_COUNT,
    )
    return db_path


if __name__ == "__main__":
    logging.basicConfig(level="INFO", format="%(message)s")
    create_sample_database()
