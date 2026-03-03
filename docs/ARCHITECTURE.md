# PhysioDiff Architecture

## Overview
PhysioDiff is a clinical decision support system built with FastAPI, designed to provide physiotherapy recommendations based on patient data and clinical analytics.

## Directory Structure
```
PhysioDiff/
├── app/                      # Main application package
│   ├── services/             # Business logic services
│   │   └── sentiment_analysis.py
│   ├── static/               # Web frontend assets
│   │   ├── index.html
│   │   ├── css/styles.css
│   │   └── js/app.js
│   ├── synthetic/            # Mock data generation
│   │   ├── mock_engine.py
│   │   └── __init__.py
│   ├── main.py              # FastAPI application entry point
│   ├── synthetic_data.py    # Data generation utilities
│   └── models.py            # Pydantic models
├── data/                     # Data directory
│   └── physio.db            # SQLite database (generated)
├── docs/                     # Documentation
│   ├── ARCHITECTURE.md      # This file
│   └── ACUHIT_Proposals.docx
├── tests/                    # Test suite
│   ├── test_api.py
│   ├── test_sentiment.py
│   └── test_*.py
├── scripts/                  # Utility scripts
│   └── validate.py
├── pyproject.toml           # Project metadata & dependencies
├── requirements.txt         # Legacy dependencies
├── README.md               # Project overview
└── .gitignore             # Git ignore patterns
```

## Key Components

### App Module
- **main.py**: FastAPI application with endpoints for clinical data processing
- **models.py**: Pydantic data models for validation
- **synthetic_data.py**: Generates mock patient and physiotherapy data

### Services
- **sentiment_analysis.py**: Analyzes text sentiment using heuristic and ML methods

### Synthetic Data Generation
- **mock_engine.py**: Creates realistic synthetic data in SQLite database

### Frontend
- **index.html**: Single-page application interface
- **css/styles.css**: Application styling
- **js/app.js**: Client-side logic and API integration

## Technology Stack
- **Backend**: FastAPI, Uvicorn, Pydantic
- **Database**: SQLite
- **Frontend**: HTML5, CSS3, JavaScript
- **ML**: scikit-learn, numpy, pandas
- **Testing**: pytest, httpx

## Database
The application uses SQLite (`data/physio.db`) for storing:
- Patient demographics
- Clinical assessments
- Physiotherapy recommendations
- Treatment outcomes

The database is generated at runtime by `mock_engine.py` if it doesn't exist.

## Running the Application
```bash
cd /sessions/epic-vigilant-tesla/mnt/PhysioDiff
pip install -r requirements.txt
PYTHONPATH=. uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Testing
```bash
cd /sessions/epic-vigilant-tesla/mnt/PhysioDiff
pip install -r requirements.txt
PYTHONPATH=. python -m pytest tests/ -v
```

## Future Improvements
- Migrate to async database operations
- Add user authentication and authorization
- Implement comprehensive logging
- Add API documentation with Swagger/OpenAPI
- Containerize with Docker
