"""
PhysioDiff FastAPI Application

Routes:
  GET  /                        — Dashboard HTML
  GET  /api/patients            — List all patients
  GET  /api/patients/{id}       — Patient detail with 7-day history
  POST /api/calculate-dhs       — Calculate DHS from vitals
  GET  /api/stats               — Summary statistics
  WS   /ws                      — Real-time risk alerts
  GET  /api/handover-report     — Download PDF handover
"""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
from typing import List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.models.dhs_algorithm import calculate_dhs
from app.models.risk_modeling import forecast_risk
from app.services.sentiment_analysis import analyze_sentiment

# ─── Constants ────────────────────────────────────────────────────────────────
_HERE = os.path.dirname(__file__)
DB_PATH = os.path.abspath(os.path.join(_HERE, "..", "data", "physio.db"))
STATIC_DIR = os.path.join(_HERE, "static")

# ─── App Setup ────────────────────────────────────────────────────────────────
app = FastAPI(title="PhysioDiff", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ─── Database Helpers ─────────────────────────────────────────────────────────
def _get_conn(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Open a database connection with Row factory."""
    if not os.path.exists(db_path):
        _ensure_database(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_database(db_path: str = DB_PATH) -> None:
    """Generate the database if it doesn't exist."""
    from app.synthetic.mock_engine import build_database
    build_database(db_path=db_path, n_patients=50, seed=42)


# ─── Pydantic Models ──────────────────────────────────────────────────────────
class VitalsInput(BaseModel):
    respiratory_rate: float
    spo2: float
    systolic_bp: float
    heart_rate: float
    temperature: float
    consciousness: int = 0
    on_supplemental_o2: bool = False
    clinical_note: str = ""
    use_llm: bool = False


# ─── WebSocket Manager ────────────────────────────────────────────────────────
class ConnectionManager:
    def __init__(self) -> None:
        self.active: List[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, message: dict) -> None:
        dead: List[WebSocket] = []
        for ws in self.active:
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()

# Track last known risk levels to detect changes
_last_risk_levels: dict[int, str] = {}


async def _alert_background_task() -> None:
    """Poll DB every 10 seconds; broadcast any risk-level changes."""
    global _last_risk_levels
    while True:
        await asyncio.sleep(10)
        if not manager.active:
            continue
        try:
            conn = _get_conn()
            rows = conn.execute(
                "SELECT id, name, risk_level, dhs_score FROM patients"
            ).fetchall()
            conn.close()

            for row in rows:
                pid = row["id"]
                new_risk = row["risk_level"]
                old_risk = _last_risk_levels.get(pid)

                if old_risk is not None and old_risk != new_risk:
                    await manager.broadcast({
                        "patient_id": pid,
                        "name": row["name"],
                        "old_risk": old_risk,
                        "new_risk": new_risk,
                        "dhs_score": row["dhs_score"],
                    })
                _last_risk_levels[pid] = new_risk
        except Exception:
            pass


@app.on_event("startup")
async def startup_event() -> None:
    if not os.path.exists(DB_PATH):
        _ensure_database()
    # Seed initial risk levels
    try:
        conn = _get_conn()
        rows = conn.execute("SELECT id, risk_level FROM patients").fetchall()
        conn.close()
        for row in rows:
            _last_risk_levels[row["id"]] = row["risk_level"]
    except Exception:
        pass
    # Start background alert task
    asyncio.create_task(_alert_background_task())


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    """Serve the glassmorphism dashboard."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>PhysioDiff Dashboard</h1><p>index.html not found</p>")


@app.get("/api/patients")
async def list_patients() -> list:
    """Return all patients with their latest risk metrics."""
    conn = _get_conn()
    rows = conn.execute(
        """SELECT id, name, ward, date_of_birth, admission_date,
                  risk_level, dhs_score, news2_score, alert_triggered
           FROM patients ORDER BY id"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/patients/{patient_id}")
async def get_patient(patient_id: int) -> dict:
    """Return a patient with their 7-day vitals history."""
    conn = _get_conn()

    patient_row = conn.execute(
        """SELECT id, name, ward, date_of_birth, admission_date,
                  risk_level, dhs_score, news2_score, alert_triggered
           FROM patients WHERE id = ?""",
        (patient_id,),
    ).fetchone()

    if patient_row is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Patient not found")

    history_rows = conn.execute(
        """SELECT timestamp, respiratory_rate, spo2, systolic_bp, heart_rate,
                  temperature, consciousness, on_supplemental_o2, clinical_note,
                  sentiment_score, news2_score, dhs_score, risk_level, alert_triggered
           FROM vitals_history WHERE patient_id = ? ORDER BY timestamp""",
        (patient_id,),
    ).fetchall()
    conn.close()

    patient = dict(patient_row)
    patient["history"] = [dict(r) for r in history_rows]
    return patient


@app.post("/api/calculate-dhs")
async def calculate_dhs_endpoint(vitals: VitalsInput) -> dict:
    """Calculate DHS from vitals input and clinical note."""
    sentiment_result = analyze_sentiment(vitals.clinical_note, use_llm=vitals.use_llm)

    dhs_result = calculate_dhs(
        respiratory_rate=vitals.respiratory_rate,
        spo2=vitals.spo2,
        systolic_bp=vitals.systolic_bp,
        heart_rate=vitals.heart_rate,
        temperature=vitals.temperature,
        consciousness=vitals.consciousness,
        on_supplemental_o2=vitals.on_supplemental_o2,
        sentiment_score=sentiment_result.score,
    )

    return {
        "dhs_score": dhs_result.dhs_score,
        "news2_score": dhs_result.news2_score,
        "risk_level": dhs_result.risk_level,
        "alert_triggered": dhs_result.alert_triggered,
        "hidden_deterioration": dhs_result.hidden_deterioration,
        "sentiment_score": sentiment_result.score,
        "sentiment_method": sentiment_result.method,
        "breakdown": {
            "rr_score": dhs_result.rr_score,
            "spo2_score": dhs_result.spo2_score,
            "sbp_score": dhs_result.sbp_score,
            "hr_score": dhs_result.hr_score,
            "temp_score": dhs_result.temp_score,
            "consciousness_score": dhs_result.consciousness_score,
            "o2_score": dhs_result.o2_score,
        },
    }


@app.get("/api/stats")
async def get_stats() -> dict:
    """Return summary statistics."""
    conn = _get_conn()

    total = conn.execute("SELECT COUNT(*) as n FROM patients").fetchone()["n"]
    active_alerts = conn.execute(
        "SELECT COUNT(*) as n FROM patients WHERE alert_triggered = 1"
    ).fetchone()["n"]

    dist_rows = conn.execute(
        "SELECT risk_level, COUNT(*) as count FROM patients GROUP BY risk_level"
    ).fetchall()
    risk_distribution = {r["risk_level"]: r["count"] for r in dist_rows}

    avg_dhs = conn.execute("SELECT AVG(dhs_score) as avg FROM patients").fetchone()["avg"]

    conn.close()

    return {
        "total_patients": total,
        "active_alerts": int(active_alerts),
        "risk_distribution": risk_distribution,
        "avg_dhs_score": round(avg_dhs or 0.0, 4),
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Real-time risk alert WebSocket."""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive; alerts are pushed by background task
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/api/handover-report")
async def handover_report() -> Response:
    """Generate and return PDF handover report for HIGH and CRITICAL patients."""
    from app.reports.handover import generate_handover_pdf

    conn = _get_conn()
    rows = conn.execute(
        """SELECT p.id, p.name, p.ward, p.risk_level, p.dhs_score, p.news2_score,
                  p.alert_triggered,
                  (SELECT clinical_note FROM vitals_history
                   WHERE patient_id = p.id ORDER BY timestamp DESC LIMIT 1) as latest_note,
                  (SELECT sentiment_score FROM vitals_history
                   WHERE patient_id = p.id ORDER BY timestamp DESC LIMIT 1) as sentiment_score
           FROM patients p
           WHERE p.risk_level IN ('HIGH', 'CRITICAL')
           ORDER BY p.dhs_score DESC"""
    ).fetchall()
    conn.close()

    # Build history for forecast
    patients = []
    conn2 = _get_conn()
    for row in rows:
        hist_rows = conn2.execute(
            """SELECT dhs_score, news2_score, sentiment_score FROM vitals_history
               WHERE patient_id = ? ORDER BY timestamp""",
            (row["id"],),
        ).fetchall()
        history = [dict(h) for h in hist_rows]
        forecast = forecast_risk(history, patient_id=str(row["id"]))

        patients.append({
            **dict(row),
            "forecast_direction": forecast.trend_direction,
            "latest_note": (row["latest_note"] or "")[:100],
        })
    conn2.close()

    pdf_bytes = generate_handover_pdf(patients)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=handover_report.pdf"},
    )
