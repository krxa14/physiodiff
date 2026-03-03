"""
Mock Engine — CLI tool to generate the PhysioDiff SQLite database.

Usage:
    PYTHONPATH=. python app/synthetic/mock_engine.py
    PYTHONPATH=. python app/synthetic/mock_engine.py --patients 50 --seed 42

Creates: app/synthetic/physio.db
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys

# Ensure project root is on the path when run directly
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from app.synthetic_data import generate_patients

DB_PATH = os.path.join(os.path.dirname(__file__), "physio.db")


def create_schema(conn: sqlite3.Connection) -> None:
    """Create database tables."""
    conn.executescript("""
        DROP TABLE IF EXISTS vitals_history;
        DROP TABLE IF EXISTS patients;

        CREATE TABLE patients (
            id               INTEGER PRIMARY KEY,
            name             TEXT NOT NULL,
            ward             TEXT NOT NULL,
            date_of_birth    TEXT,
            admission_date   TEXT,
            risk_profile     TEXT,
            risk_level       TEXT,
            dhs_score        REAL,
            news2_score      INTEGER,
            alert_triggered  INTEGER DEFAULT 0
        );

        CREATE TABLE vitals_history (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id          INTEGER NOT NULL,
            timestamp           TEXT NOT NULL,
            respiratory_rate    REAL,
            spo2                REAL,
            systolic_bp         REAL,
            heart_rate          REAL,
            temperature         REAL,
            consciousness       INTEGER,
            on_supplemental_o2  INTEGER DEFAULT 0,
            clinical_note       TEXT,
            sentiment_score     REAL,
            news2_score         INTEGER,
            dhs_score           REAL NOT NULL,
            risk_level          TEXT NOT NULL,
            alert_triggered     INTEGER DEFAULT 0,
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        );
    """)
    conn.commit()


def populate_database(conn: sqlite3.Connection, n_patients: int = 50, seed: int = 42) -> int:
    """Generate and insert patients + vitals. Returns number of vitals records inserted."""
    patients = generate_patients(n_patients=n_patients, seed=seed)

    vitals_count = 0

    for p in patients:
        conn.execute(
            """INSERT INTO patients
               (id, name, ward, date_of_birth, admission_date,
                risk_profile, risk_level, dhs_score, news2_score, alert_triggered)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                p["id"],
                p["name"],
                p["ward"],
                p["date_of_birth"],
                p["admission_date"],
                p["risk_profile"],
                p["risk_level"],
                p["dhs_score"],
                p["news2_score"],
                int(p["alert_triggered"]),
            ),
        )

        for record in p["vitals_history"]:
            conn.execute(
                """INSERT INTO vitals_history
                   (patient_id, timestamp, respiratory_rate, spo2, systolic_bp,
                    heart_rate, temperature, consciousness, on_supplemental_o2,
                    clinical_note, sentiment_score, news2_score, dhs_score,
                    risk_level, alert_triggered)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    p["id"],
                    record["timestamp"],
                    record["respiratory_rate"],
                    record["spo2"],
                    record["systolic_bp"],
                    record["heart_rate"],
                    record["temperature"],
                    record["consciousness"],
                    int(record["on_supplemental_o2"]),
                    record["clinical_note"],
                    record["sentiment_score"],
                    record["news2_score"],
                    record["dhs_score"],
                    record["risk_level"],
                    int(record["alert_triggered"]),
                ),
            )
            vitals_count += 1

    conn.commit()
    return vitals_count


def build_database(db_path: str = DB_PATH, n_patients: int = 50, seed: int = 42) -> int:
    """Build the database at the given path. Returns vitals record count."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # dict-style access

    try:
        create_schema(conn)
        count = populate_database(conn, n_patients=n_patients, seed=seed)
    finally:
        conn.close()

    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="PhysioDiff Mock Database Generator")
    parser.add_argument("--patients", type=int, default=50, help="Number of patients (default: 50)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    parser.add_argument("--db", type=str, default=DB_PATH, help="Output database path")
    args = parser.parse_args()

    print(f"Generating {args.patients} patients (seed={args.seed})...")
    count = build_database(db_path=args.db, n_patients=args.patients, seed=args.seed)

    db_size = os.path.getsize(args.db) / 1024
    print(f"Inserted {count} vitals records")
    print(f"Database created: {args.db} ({db_size:.1f} KB)")

    if db_size < 50:
        print("WARNING: Database is smaller than expected (< 50 KB)")
    else:
        print("SUCCESS: Database size OK")


if __name__ == "__main__":
    main()
