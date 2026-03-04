# PhysioDiff — Clinical Decision Support System

> **ACUHIT Hackathon 2026** · Delta Homeostasis Score · Hidden Deterioration Detection

PhysioDiff detects **hidden clinical deterioration** — patients whose NEWS2 vital-signs score looks stable but whose clinical notes reveal decline. The DHS algorithm catches this signal **12–24 hours earlier** than traditional alarms.

---

## The Problem

Standard escalation tools like NEWS2 rely entirely on vital signs. A patient with deteriorating mental state, laboured breathing described in nursing notes, or worsening subjective reports will score LOW on NEWS2 — and receive no alert — until their physiology visibly collapses.

## The Solution: DHS (Delta Homeostasis Score)

```
DHS = 0.65 × NEWS2_normalized + 0.35 × sentiment_score
```

When **NEWS2 < 3** (vitals appear normal) AND **sentiment < −0.4** (notes signal distress), PhysioDiff raises a **Hidden Deterioration** alert — before any alarm would normally fire.

---

## Quick Start

```bash
# 1 — Install dependencies
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2 — Generate synthetic patient database (50 patients × 7 days)
PYTHONPATH=. python app/synthetic/mock_engine.py --patients 50 --seed 42

# 3 — Start the server
PYTHONPATH=. uvicorn app.main:app --reload --port 8000

# Open http://localhost:8000
```

---

## Project Structure

```
PhysioDiff/
├── app/
│   ├── main.py                  FastAPI backend — 7 endpoints + WebSocket
│   ├── sentiment_analysis.py    Heuristic NLP + Ollama phi3:mini fallback
│   ├── synthetic_data.py        Patient / vitals generation primitives
│   ├── models/
│   │   ├── dhs_algorithm.py     NEWS2 scoring + DHS calculation  ← CORE
│   │   └── risk_modeling.py     RandomForest 12h/24h risk forecasting
│   ├── reports/
│   │   └── handover.py          PDF handover report (reportlab)
│   ├── static/
│   │   └── index.html           White clinical dashboard (vanilla JS)
│   └── synthetic/
│       └── mock_engine.py       CLI — generates SQLite DB
├── scripts/
│   └── validate.py              End-to-end smoke tests (6 checks)
├── tests/                       pytest suite — 135 tests, ≥80% coverage
│   ├── test_dhs_algorithm.py
│   ├── test_risk_modeling.py
│   ├── test_sentiment.py
│   ├── test_mock_engine.py
│   └── test_api.py
├── requirements.txt
```

--

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/` | Clinical dashboard (HTML) |
| `GET`  | `/api/patients` | All 50 patients with current risk |
| `GET`  | `/api/patients/{id}` | Patient detail + 7-day history |
| `POST` | `/api/calculate-dhs` | Calculate DHS from vitals input |
| `GET`  | `/api/stats` | Summary statistics + risk distribution |
| `WS`   | `/ws` | Real-time risk-change alerts |
| `GET`  | `/api/handover-report` | Download PDF handover |

---

## NEWS2 Scoring Reference

| Vital | Score |
|-------|-------|
| Respiratory Rate | ≤8→3, 9–11→1, 12–20→0, 21–24→2, ≥25→3 |
| SpO₂ (Scale 1) | ≤91→3, 92–93→2, 94–95→1, ≥96→0 |
| Systolic BP | ≤90→3, 91–100→2, 101–110→1, 111–219→0, ≥220→3 |
| Heart Rate | ≤40→3, 41–50→1, 51–90→0, 91–110→1, 111–130→2, ≥131→3 |
| Temperature | ≤35.0→3, 35.1–36.0→1, 36.1–38.0→0, 38.1–39.0→1, ≥39.1→2 |
| Consciousness | Alert→0, V/P/U→3 |
| Supplemental O₂ | On O₂→2, Air→0 |

**Risk Levels:** ≥7 CRITICAL · 5–6 HIGH · 3–4 MEDIUM · 0–2 LOW · 0–2 + hidden det → MEDIUM alert

---

## DHS Algorithm Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| `news2_weight` | **0.65** | Physiology is objective and reliable |
| `sentiment_weight` | **0.35** | Adds early-warning signal, noisier |
| Hidden det NEWS2 threshold | **< 3** | Vitals appear normal |
| Hidden det sentiment threshold | **< −0.4** | Strong negative required — avoids false positives |

---

## Testing

```bash
# Full test suite
PYTHONPATH=. pytest tests/ -v --cov=app --cov-report=term-missing

# End-to-end validation (requires running server)
PYTHONPATH=. python scripts/validate.py
```

**Status:** 135 tests passing · validate.py 6/6

---

## Dashboard Features

- **Three-panel white clinical layout** — patient list · detail · calculator
- **Hidden Deterioration banner** — fires when NEWS2 < 3 + sentiment < −0.4
- **Tabbed vital charts** — DHS · RR · SpO₂ · BP · HR · Temp with normal-zone bands
- **DHS Calculator** — zone-coloured sliders, live numeric result, NEWS2 breakdown bars
- **Real-time WebSocket alerts** — toast notifications on risk-level changes
- **PDF Handover report** — one-click download for ward handover

---

## Known Limitations

- Ollama LLM requires a local Ollama server; heuristic fallback is used by default
- RandomForest trained on 7 records has low confidence — trend detection is primarily statistical
- SQLite is not suitable for concurrent production access — use PostgreSQL for multi-user deployment
- WebSocket alerts broadcast to all clients (no per-user filtering)
