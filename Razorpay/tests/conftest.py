"""Shared pytest fixtures for the commerce engine tests."""

import os
import sys
import json
import sqlite3
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


@pytest.fixture(scope="function")
def test_db(tmp_path):
    """Create a temporary SQLite database for testing."""
    db_path = str(tmp_path / "test_commerce.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

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

    conn.commit()
    yield conn, db_path
    conn.close()


@pytest.fixture(scope="function")
def seeded_db(test_db):
    """Database pre-populated with mock products."""
    conn, db_path = test_db
    cursor = conn.cursor()

    products = [
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
    ''', products)

    conn.commit()
    yield conn, db_path


@pytest.fixture(scope="function")
def mock_razorpay():
    """Mock Razorpay service that returns a fake order."""
    mock_service = MagicMock()
    mock_service.create_order.return_value = {
        'id': 'order_test_123456',
        'amount': 59900,
        'currency': 'INR',
        'status': 'created',
        'receipt': 'rcpt_test123'
    }
    return mock_service


@pytest.fixture(scope="function")
def test_client(seeded_db, mock_razorpay):
    """FastAPI TestClient with mocked database and Razorpay."""
    conn, db_path = seeded_db

    # Set env vars before any imports that use config
    env_vars = {
        'RAZORPAY_KEY_ID': 'rzp_test_fake',
        'RAZORPAY_KEY_SECRET': 'fake_secret',
        'MAX_TRANSACTION_AMOUNT': '500000',
        'AGENT_POLL_INTERVAL': '10',
    }

    with patch.dict(os.environ, env_vars):
        # Clear config cache so it picks up test env vars
        from backend.config import get_settings
        get_settings.cache_clear()

        # Import the checkout module to patch its get_razorpay_service reference
        import backend.routes.checkout as checkout_module
        import backend.database as database_module

        # Patch DB_PATH at the source and the razorpay service at usage site
        with patch.object(database_module, 'DB_PATH', db_path), \
             patch.object(checkout_module, 'get_razorpay_service', return_value=mock_razorpay):

            from backend.main import app
            client = TestClient(app)
            yield client

        get_settings.cache_clear()
