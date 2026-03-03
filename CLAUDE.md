# PhysioDiff — Project Specification

## Overview
PhysioDiff is a clinical decision support system that detects **Hidden Deterioration**: patients whose NEWS2 vital signs score looks stable but whose clinical notes (analyzed via NLP sentiment) reveal decline. The DHS (Delta Homeostasis Score) catches this 12–24 hours earlier than traditional alarms.

## Architecture

```
app/
  main.py                     # FastAPI app — 6+ routes
  synthetic_data.py           # Patient + vitals generation
  sentiment_analysis.py       # Ollama phi3:mini + heuristic fallback
  models/
    dhs_algorithm.py          # NEWS2 + DHS calculation — CORE LOGIC
    risk_modeling.py          # RandomForest 12/24h forecast
  synthetic/
    mock_engine.py            # CLI: generates SQLite DB
  static/
    index.html                # Glassmorphism dashboard
  reports/
    handover.py               # PDF handover report generator
```

## Key Constants (DO NOT CHANGE without explicit instruction)

| Constant | Value | Rationale |
|----------|-------|-----------|
| DHS news2_weight | 0.65 | Physiological data is more objective and reliable |
| DHS sentiment_weight | 0.35 | Sentiment adds early warning signal but is noisier |
| Hidden deterioration NEWS2 threshold | < 3 | Below this, vitals appear normal — only sentiment signals risk |
| Hidden deterioration sentiment threshold | < -0.4 | Strong negative signal required to avoid false positives |
| Synthetic patients | 50 | Large enough for credible risk distribution, fast to generate |
| History per patient | 7 days | Minimum window for RandomForest trend detection |
| RandomForest n_estimators | 50 | CPU-efficient; adequate for 7-record training window |

## Running the System

```bash
# Generate database
PYTHONPATH=. python app/synthetic/mock_engine.py --patients 50 --seed 42

# Start server
PYTHONPATH=. uvicorn app.main:app --reload --port 8000

# Run tests
PYTHONPATH=. pytest tests/ -v --cov=app --cov-report=term-missing

# Validate
PYTHONPATH=. python scripts/validate.py
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | / | Dashboard HTML |
| GET | /api/patients | List all 50 patients |
| GET | /api/patients/{id} | Patient detail with 7-day history |
| POST | /api/calculate-dhs | Calculate DHS from vitals input |
| GET | /api/stats | Summary statistics |
| WS | /ws | Real-time risk alerts |
| GET | /api/handover-report | Download PDF handover |

## NEWS2 Scoring

| Parameter | Ranges → Score |
|-----------|---------------|
| Respiratory Rate | ≤8→3, 9-11→1, 12-20→0, 21-24→2, ≥25→3 |
| SpO2 (Scale 1) | ≤91→3, 92-93→2, 94-95→1, ≥96→0 |
| Systolic BP | ≤90→3, 91-100→2, 101-110→1, 111-219→0, ≥220→3 |
| Heart Rate | ≤40→3, 41-50→1, 51-90→0, 91-110→1, 111-130→2, ≥131→3 |
| Temperature | ≤35.0→3, 35.1-36.0→1, 36.1-38.0→0, 38.1-39.0→1, ≥39.1→2 |
| Consciousness | Alert(0)→0, V/P/U(1)→3 |
| Supplemental O2 | On O2→2, Air→0 |

## Risk Levels

| NEWS2 | Risk Level |
|-------|-----------|
| ≥ 7 | CRITICAL |
| 5-6 | HIGH |
| 3-4 | MEDIUM |
| 0-2 | LOW |
| 0-2 + hidden deterioration | MEDIUM (alert) |

## What Was Fixed
- Created all source files from scratch (project was scaffolded but no files existed)
- Added `__init__.py` files to all packages
- Ensured all numeric Pydantic fields use `float` type
- Fixed SQLite row factory for dict-style access
- Added PYTHONPATH handling in mock_engine.py

## What Was Added
- Full FastAPI backend with 7 endpoints
- WebSocket real-time alerts (background task polls DB every 10s)
- PDF handover report via reportlab
- Glassmorphism frontend dashboard
- Complete pytest test suite with ≥80% coverage
- scripts/validate.py end-to-end smoke test

## Known Limitations
- Ollama LLM requires local Ollama server; heuristic fallback is used by default
- RandomForest with 7 records has low confidence; trend detection is primarily statistical
- SQLite is not suitable for production concurrent access; use PostgreSQL for multi-user deployment
- WebSocket alerts are broadcast to all connected clients (no per-user filtering)
