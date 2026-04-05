# This module saves and reads QC results from a local SQLite database.
# SQLite is a file-based database. No server setup is needed.
# The database file is stored at data/aria.db.

import sqlite3
import os
from typing import List, Dict

# Path to the database file
DB_PATH = os.environ.get("DB_PATH", "data/aria.db")


def init_db(db_path: str = DB_PATH) -> None:
    """
    This function creates the database table if it does not exist yet.
    It is safe to call this function every time the app starts.
    """
    os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create the table for QC results
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS qc_results (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            instrument_id TEXT    NOT NULL,
            test_name     TEXT    NOT NULL,
            qc_level      TEXT    NOT NULL,
            z_score       REAL    NOT NULL,
            status        TEXT    NOT NULL,
            timestamp     TEXT    NOT NULL,
            created_at    TEXT    DEFAULT (datetime('now'))
        )
    """)

    conn.commit()
    conn.close()


def save_result(row_dict: Dict, db_path: str = DB_PATH) -> None:
    """
    This function saves one QC result to the database.
    Pass a dictionary with keys: instrument_id, test_name, qc_level,
    z_score, status, timestamp.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO qc_results
            (instrument_id, test_name, qc_level, z_score, status, timestamp)
        VALUES
            (:instrument_id, :test_name, :qc_level, :z_score, :status, :timestamp)
    """, row_dict)

    conn.commit()
    conn.close()


def get_recent(limit: int = 100, db_path: str = DB_PATH) -> List[Dict]:
    """
    This function reads the most recent QC results from the database.
    Returns a list of dictionaries, newest results first.
    """
    if not os.path.exists(db_path):
        return []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # return rows as dicts
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, instrument_id, test_name, qc_level, z_score, status, timestamp, created_at
        FROM qc_results
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))

    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows
