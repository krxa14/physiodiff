"""Tests for the mock database engine."""
import os
import sqlite3
import tempfile
import pytest

from app.synthetic.mock_engine import build_database, create_schema, populate_database


@pytest.fixture
def temp_db(tmp_path):
    """Provide a temporary database path."""
    return str(tmp_path / "test_physio.db")


class TestBuildDatabase:
    def test_generates_correct_vitals_count(self, temp_db):
        count = build_database(db_path=temp_db, n_patients=10, seed=42)
        assert count == 70  # 10 patients × 7 records

    def test_db_file_exists(self, temp_db):
        build_database(db_path=temp_db, n_patients=10, seed=42)
        assert os.path.exists(temp_db)

    def test_350_records_for_50_patients(self, temp_db):
        count = build_database(db_path=temp_db, n_patients=50, seed=42)
        assert count == 350

    def test_db_contains_patients_table(self, temp_db):
        build_database(db_path=temp_db, n_patients=5, seed=42)
        conn = sqlite3.connect(temp_db)
        tables = {
            row[0] for row in
            conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        conn.close()
        assert "patients" in tables

    def test_db_contains_vitals_history_table(self, temp_db):
        build_database(db_path=temp_db, n_patients=5, seed=42)
        conn = sqlite3.connect(temp_db)
        tables = {
            row[0] for row in
            conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        conn.close()
        assert "vitals_history" in tables


class TestDatabaseContent:
    def test_no_null_dhs_scores(self, temp_db):
        build_database(db_path=temp_db, n_patients=10, seed=42)
        conn = sqlite3.connect(temp_db)
        nulls = conn.execute(
            "SELECT COUNT(*) FROM vitals_history WHERE dhs_score IS NULL"
        ).fetchone()[0]
        conn.close()
        assert nulls == 0

    def test_no_null_risk_levels(self, temp_db):
        build_database(db_path=temp_db, n_patients=10, seed=42)
        conn = sqlite3.connect(temp_db)
        nulls = conn.execute(
            "SELECT COUNT(*) FROM vitals_history WHERE risk_level IS NULL"
        ).fetchone()[0]
        conn.close()
        assert nulls == 0

    def test_risk_distribution_non_degenerate(self, temp_db):
        """At least 2 different risk levels present."""
        build_database(db_path=temp_db, n_patients=50, seed=42)
        conn = sqlite3.connect(temp_db)
        distinct = conn.execute(
            "SELECT COUNT(DISTINCT risk_level) FROM patients"
        ).fetchone()[0]
        conn.close()
        assert distinct >= 2

    def test_vitals_count_matches_patients(self, temp_db):
        build_database(db_path=temp_db, n_patients=10, seed=42)
        conn = sqlite3.connect(temp_db)
        n_patients = conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
        n_vitals = conn.execute("SELECT COUNT(*) FROM vitals_history").fetchone()[0]
        conn.close()
        assert n_patients == 10
        assert n_vitals == 70

    def test_all_patients_have_risk_level(self, temp_db):
        build_database(db_path=temp_db, n_patients=10, seed=42)
        conn = sqlite3.connect(temp_db)
        invalid = conn.execute(
            "SELECT COUNT(*) FROM patients WHERE risk_level NOT IN ('LOW','MEDIUM','HIGH','CRITICAL')"
        ).fetchone()[0]
        conn.close()
        assert invalid == 0

    def test_dhs_scores_in_valid_range(self, temp_db):
        build_database(db_path=temp_db, n_patients=10, seed=42)
        conn = sqlite3.connect(temp_db)
        invalid = conn.execute(
            "SELECT COUNT(*) FROM vitals_history WHERE dhs_score < 0 OR dhs_score > 1"
        ).fetchone()[0]
        conn.close()
        assert invalid == 0

    def test_each_patient_has_7_records(self, temp_db):
        build_database(db_path=temp_db, n_patients=10, seed=42)
        conn = sqlite3.connect(temp_db)
        rows = conn.execute(
            "SELECT patient_id, COUNT(*) as cnt FROM vitals_history GROUP BY patient_id"
        ).fetchall()
        conn.close()
        assert all(row[1] == 7 for row in rows)


class TestSchema:
    def test_create_schema_idempotent(self, temp_db):
        """create_schema can be called twice without error."""
        conn = sqlite3.connect(temp_db)
        create_schema(conn)
        create_schema(conn)
        conn.close()

    def test_foreign_key_relationship(self, temp_db):
        build_database(db_path=temp_db, n_patients=5, seed=1)
        conn = sqlite3.connect(temp_db)
        orphans = conn.execute(
            """SELECT COUNT(*) FROM vitals_history
               WHERE patient_id NOT IN (SELECT id FROM patients)"""
        ).fetchone()[0]
        conn.close()
        assert orphans == 0
