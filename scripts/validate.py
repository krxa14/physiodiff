"""
PhysioDiff Validation Script — Phase 04

Performs 6 automated end-to-end smoke tests against the running server.
All 6 checks must print PASS. Any FAIL stops the release.

Usage:
    PYTHONPATH=. python scripts/validate.py
"""
from __future__ import annotations

import sys
import requests

BASE_URL = "http://localhost:8000"
PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"


def check(name: str, condition: bool, detail: str = "") -> bool:
    status = PASS if condition else FAIL
    suffix = f"  ({detail})" if detail else ""
    print(f"[{status}] {name}{suffix}")
    return condition


def main() -> None:
    print("\nPhysioDiff Validation — Phase 04")
    print("=" * 50)
    all_pass = True

    # ── Check 1: GET /api/stats ─────────────────────────────────────────────
    try:
        resp = requests.get(f"{BASE_URL}/api/stats", timeout=10)
        data = resp.json()
        ok = resp.status_code == 200 and isinstance(data.get("active_alerts"), int)
        all_pass &= check("GET /api/stats → active_alerts is int", ok,
                          f"status={resp.status_code}, active_alerts={data.get('active_alerts')}")
    except Exception as e:
        all_pass &= check("GET /api/stats → active_alerts is int", False, str(e))

    # ── Check 2: GET /api/patients ──────────────────────────────────────────
    try:
        resp = requests.get(f"{BASE_URL}/api/patients", timeout=10)
        data = resp.json()
        has_risk = all("risk_level" in p for p in data)
        ok = resp.status_code == 200 and len(data) == 50 and has_risk
        all_pass &= check("GET /api/patients → 50 patients with risk_level", ok,
                          f"count={len(data)}, all_have_risk_level={has_risk}")
    except Exception as e:
        all_pass &= check("GET /api/patients → 50 patients with risk_level", False, str(e))

    # ── Check 3: POST critical patient ─────────────────────────────────────
    try:
        payload = {
            "respiratory_rate": 28.0,
            "spo2": 88.0,
            "systolic_bp": 88.0,
            "heart_rate": 128.0,
            "temperature": 38.5,
            "clinical_note": "acutely distressed, diaphoretic",
        }
        resp = requests.post(f"{BASE_URL}/api/calculate-dhs", json=payload, timeout=10)
        data = resp.json()
        ok = resp.status_code == 200 and data.get("risk_level") == "CRITICAL"
        all_pass &= check(
            "POST /api/calculate-dhs critical → risk_level=CRITICAL", ok,
            f"risk_level={data.get('risk_level')}, news2={data.get('news2_score')}"
        )
    except Exception as e:
        all_pass &= check("POST /api/calculate-dhs critical → risk_level=CRITICAL", False, str(e))

    # ── Check 4: POST stable patient ────────────────────────────────────────
    try:
        payload = {
            "respiratory_rate": 16.0,
            "spo2": 97.0,
            "systolic_bp": 122.0,
            "heart_rate": 72.0,
            "temperature": 37.0,
            "clinical_note": "alert and oriented, tolerating diet",
        }
        resp = requests.post(f"{BASE_URL}/api/calculate-dhs", json=payload, timeout=10)
        data = resp.json()
        ok = resp.status_code == 200 and data.get("risk_level") == "LOW"
        all_pass &= check(
            "POST /api/calculate-dhs stable → risk_level=LOW", ok,
            f"risk_level={data.get('risk_level')}"
        )
    except Exception as e:
        all_pass &= check("POST /api/calculate-dhs stable → risk_level=LOW", False, str(e))

    # ── Check 5: POST hidden deterioration ──────────────────────────────────
    try:
        payload = {
            "respiratory_rate": 17.0,
            "spo2": 96.0,
            "systolic_bp": 118.0,
            "heart_rate": 80.0,
            "temperature": 37.1,
            "clinical_note": "confused agitated laboured breathing",
        }
        resp = requests.post(f"{BASE_URL}/api/calculate-dhs", json=payload, timeout=10)
        data = resp.json()
        ok = resp.status_code == 200 and data.get("alert_triggered") is True
        all_pass &= check(
            "POST /api/calculate-dhs hidden deterioration → alert_triggered=True", ok,
            f"alert_triggered={data.get('alert_triggered')}, sentiment={data.get('sentiment_score')}"
        )
    except Exception as e:
        all_pass &= check("POST /api/calculate-dhs hidden deterioration → alert_triggered=True",
                          False, str(e))

    # ── Check 6: GET /api/handover-report ───────────────────────────────────
    try:
        resp = requests.get(f"{BASE_URL}/api/handover-report", timeout=30)
        is_pdf = resp.status_code == 200 and "pdf" in resp.headers.get("content-type", "")
        all_pass &= check(
            "GET /api/handover-report → Content-Type application/pdf", is_pdf,
            f"status={resp.status_code}, content-type={resp.headers.get('content-type')}"
        )
    except Exception as e:
        all_pass &= check("GET /api/handover-report → Content-Type application/pdf",
                          False, str(e))

    # ── Summary ──────────────────────────────────────────────────────────────
    print("=" * 50)
    if all_pass:
        print("\n✓ All 6 checks PASSED — ready for release\n")
        sys.exit(0)
    else:
        print("\n✗ One or more checks FAILED — do not release\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
