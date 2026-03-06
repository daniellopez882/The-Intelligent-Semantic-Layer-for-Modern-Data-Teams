import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import random
import os

def create_sample_database(db_path: str = "ecommerce.db"):
    """Create high-fidelity sample database for client demonstrations"""
    
    if os.path.exists(db_path):
        os.remove(db_path)
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Schema Definition
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        customer_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE,
        segment TEXT,
        country TEXT,
        signup_date DATE
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        product_id INTEGER PRIMARY KEY,
        product_name TEXT NOT NULL,
        category TEXT,
        sub_category TEXT,
        base_price DECIMAL(10, 2)
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
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
    )
    """)
    
    # 2. Rich Seed Data
    segments = ['Corporate', 'Retail', 'Wholesale', 'Affiliate']
    countries = ['USA', 'UK', 'Germany', 'Canada', 'France', 'Japan', 'Australia', 'Brazil']
    
    customer_data = []
    first_names = ["James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis"]
    
    for i in range(1, 41):
        name = f"{random.choice(first_names)} {random.choice(last_names)}"
        customer_data.append((
            i, name, f"{name.lower().replace(' ', '.')}.{i}@demo.io", 
            random.choice(segments), random.choice(countries),
            (datetime.now() - timedelta(days=random.randint(200, 700))).strftime('%Y-%m-%d')
        ))
    
    product_catalog = [
        (1, 'Quantum Laptop Pro', 'Electronics', 'Computing', 1499.99),
        (2, 'Neural Mouse', 'Electronics', 'Peripherals', 89.00),
        (3, 'ErgoDesk 3000', 'Furniture', 'Office', 599.99),
        (4, 'Crystal Display 4K', 'Electronics', 'Computing', 649.99),
        (5, 'Haptic Keyboard', 'Electronics', 'Peripherals', 129.50),
        (6, 'Aero-Mesh Chair', 'Furniture', 'Office', 349.00),
        (7, 'SmartBrew Elite', 'Appliances', 'Kitchen', 199.99),
        (8, 'Sonic Buds V2', 'Electronics', 'Audio', 159.00),
        (9, 'Titan Smartphone', 'Electronics', 'Mobile', 999.00),
        (10, 'Zen Tablet 12', 'Electronics', 'Mobile', 499.00),
        (11, 'Gourmet Grinder', 'Appliances', 'Kitchen', 59.99),
        (12, 'Studio Monitor Pro', 'Electronics', 'Audio', 299.00),
    ]
    
    cursor.executemany("INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?)", customer_data)
    cursor.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?)", product_catalog)
    
    # 3. Dynamic Order Generation (Time-Series Friendly)
    orders = []
    statuses = ['Delivered', 'Shipped', 'Processing', 'Cancelled']
    
    for i in range(1, 251): # 250 orders
        cust_id = random.randint(1, 40)
        prod = random.choice(product_catalog)
        qty = random.randint(1, 5)
        
        # Logic: More recent orders have higher quantity or frequency
        days_ago = random.randint(0, 180)
        order_date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d')
        
        unit_p = prod[4]
        # Random small discount/markup for realistic pricing
        unit_p = round(unit_p * random.uniform(0.9, 1.1), 2)
        total = round(unit_p * qty, 2)
        
        orders.append((
            i, cust_id, prod[0], order_date, qty, unit_p, total, random.choice(statuses)
        ))
    
    cursor.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?)", orders)
    
    conn.commit()
    conn.close()
    
    print(f"💎 Demo Intelligence Core Reconstructed: {db_path}")
    print(f"📊 Matrix: 40 Customers | 12 Product Lines | 250 Transaction Records")

if __name__ == "__main__":
    create_sample_database()
