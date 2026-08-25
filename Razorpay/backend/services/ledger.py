import os
import json
import sqlite3
from typing import List
from backend.models import LedgerEntry

LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'transactions.log')

def log_transaction(entry: LedgerEntry, db_conn: sqlite3.Connection) -> LedgerEntry:
    """Logs a transaction to both a JSON file and the SQLite database."""
    # Write to JSON file
    with open(LOG_FILE, 'a') as f:
        f.write(entry.model_dump_json() + '\n')
        
    # Insert into database
    cursor = db_conn.cursor()
    cursor.execute('''
        INSERT INTO transactions 
        (timestamp, trigger_reason, skus, cart_value_paise, razorpay_order_id, status, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        entry.timestamp,
        entry.trigger_reason,
        json.dumps(entry.skus),
        entry.cart_value_paise,
        entry.razorpay_order_id,
        entry.status,
        entry.error_message
    ))
    db_conn.commit()
    
    entry.id = cursor.lastrowid
    return entry

def get_all_transactions(db_conn: sqlite3.Connection) -> List[LedgerEntry]:
    """Retrieves all transactions from the SQLite database."""
    cursor = db_conn.cursor()
    cursor.execute('SELECT * FROM transactions')
    rows = cursor.fetchall()
    
    entries = []
    for row in rows:
        row_dict = dict(row)
        # Parse SKUs back from JSON string
        row_dict['skus'] = json.loads(row_dict['skus'])
        entries.append(LedgerEntry(**row_dict))
        
    return entries
