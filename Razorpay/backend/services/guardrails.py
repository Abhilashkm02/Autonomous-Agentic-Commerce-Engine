import sqlite3
from typing import List
from backend.config import get_settings
from backend.models import CheckoutItem

class SpendingLimitExceeded(Exception):
    """Exception raised when spending limit is exceeded."""
    def __init__(self, amount_paise: int, max_paise: int):
        self.amount_paise = amount_paise
        self.max_paise = max_paise
        super().__init__(f"Spending limit exceeded. Attempted: {amount_paise}, Max allowed: {max_paise}")

def enforce_limits(total_paise: int, max_paise: int = None):
    """Enforces the maximum transaction amount limit."""
    if max_paise is None:
        settings = get_settings()
        max_paise = settings.MAX_TRANSACTION_AMOUNT
        
    if total_paise > max_paise:
        raise SpendingLimitExceeded(amount_paise=total_paise, max_paise=max_paise)

def validate_cart_items(items: List[CheckoutItem], db_connection: sqlite3.Connection):
    """Validates that all SKUs in the cart exist and have sufficient stock."""
    cursor = db_connection.cursor()
    for item in items:
        cursor.execute('SELECT * FROM products WHERE sku = ?', (item.sku,))
        row = cursor.fetchone()
        
        if not row:
            raise ValueError(f"Product with SKU {item.sku} does not exist.")
            
        stock = row['stock']
        if stock < item.quantity:
            raise ValueError(f"Insufficient stock for SKU {item.sku}. Requested: {item.quantity}, Available: {stock}")
