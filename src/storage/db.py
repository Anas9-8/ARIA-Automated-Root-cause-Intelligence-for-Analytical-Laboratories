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
    Create the QC result table if missing. Safe to call on every app start.
    A UNIQUE index on (instrument_id, test_name, qc_level, timestamp) lets
    save_result() be idempotent — re-saving the same QC outcome is a no-op.
    """
    os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

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
    # Pre-existing databases may already hold duplicate rows from before
    # save_result() was idempotent. Dedupe before creating the unique index.
    cursor.execute("""
        DELETE FROM qc_results
        WHERE id NOT IN (
            SELECT MIN(id) FROM qc_results
            GROUP BY instrument_id, test_name, qc_level, timestamp
        )
    """)
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_qc_results_group_ts
        ON qc_results (instrument_id, test_name, qc_level, timestamp)
    """)

    conn.commit()
    conn.close()


def save_result(row_dict: Dict, db_path: str = DB_PATH) -> None:
    """
    Save one QC result. Idempotent — repeated saves of the same
    (instrument, test, level, timestamp) are silently ignored thanks to the
    unique index above. This makes hitting /qc/status repeatedly safe.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR IGNORE INTO qc_results
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
