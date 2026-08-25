"""SQLite database manager for the commerce engine."""

import os
import sqlite3
from typing import Optional
from contextlib import contextmanager
from backend.models import Product

DB_PATH = os.path.join(os.path.dirname(__file__), 'db', 'commerce.db')


def init_db() -> None:
    """Initializes the database, creating tables and seeding data if empty."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # Create products table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                price_paise INTEGER NOT NULL,
                stock INTEGER NOT NULL,
                reorder_threshold INTEGER NOT NULL,
                category TEXT NOT NULL
            )
        ''')

        # Create transactions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                trigger_reason TEXT NOT NULL,
                skus TEXT NOT NULL,
                cart_value_paise INTEGER NOT NULL,
                razorpay_order_id TEXT,
                status TEXT NOT NULL,
                error_message TEXT
            )
        ''')

        # Check if products exist
        cursor.execute('SELECT COUNT(*) FROM products')
        count = cursor.fetchone()[0]

        if count == 0:
            products_to_seed = [
                ('SKU-ELEC-001', 'Wireless Mouse', 59900, 5, 10, 'Electronics'),
                ('SKU-ELEC-002', 'Mechanical Keyboard', 249900, 3, 5, 'Electronics'),
                ('SKU-ELEC-003', 'USB-C Hub', 189900, 8, 10, 'Electronics'),
                ('SKU-ELEC-004', 'Webcam HD 1080p', 149900, 2, 5, 'Electronics'),
                ('SKU-OFFC-001', 'A4 Paper Ream (500 sheets)', 34900, 15, 20, 'Office Supplies'),
                ('SKU-OFFC-002', 'Whiteboard Markers (Pack of 10)', 19900, 25, 30, 'Office Supplies'),
                ('SKU-OFFC-003', 'Desk Organizer', 79900, 4, 8, 'Office Supplies'),
                ('SKU-TECH-001', 'HDMI Cable 2m', 29900, 12, 15, 'Tech Accessories'),
                ('SKU-TECH-002', 'Laptop Stand Adjustable', 199900, 6, 8, 'Tech Accessories'),
                ('SKU-TECH-003', 'Surge Protector 6-Outlet', 89900, 7, 10, 'Tech Accessories'),
            ]

            cursor.executemany('''
                INSERT INTO products (sku, name, price_paise, stock, reorder_threshold, category)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', products_to_seed)

        conn.commit()


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def get_all_products(conn: sqlite3.Connection) -> list[Product]:
    """Retrieves all products from the database."""
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM products')
    rows = cursor.fetchall()
    return [Product(**dict(row)) for row in rows]


def get_product_by_sku(conn: sqlite3.Connection, sku: str) -> Optional[Product]:
    """Retrieves a product by its SKU."""
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM products WHERE sku = ?', (sku,))
    row = cursor.fetchone()
    if row:
        return Product(**dict(row))
    return None


def update_stock(conn: sqlite3.Connection, sku: str, quantity_to_deduct: int) -> None:
    """Deducts the specified quantity from the stock of the product with the given SKU."""
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE products
        SET stock = stock - ?
        WHERE sku = ?
    ''', (quantity_to_deduct, sku))
    conn.commit()
