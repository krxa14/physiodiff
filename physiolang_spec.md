# PhysioDiff: Championship-Level Technical Spec
## ACUHIT Hackathon 2026 - Official Submission Strategy

### 1. Executive Summary
PhysioDiff is a next-generation clinical decision support system. It maps the delta between **standardized physiological scores (NEWS2)** and **qualitative clinical sentiment** extracted from physician notes. This allows for the identification of "Hidden Deterioration"—patients whose vitals look stable but whose clinical notes indicate a subjective decline.

### 2. The Core Innovation: The DHS Matrix
Instead of a single score, PhysioDiff generates a 2D Matrix:
- **NEWS2 Axis**: Quantifiable risk (Heart rate, BP, O2 Sat, Temp, RR).
- **Sentiment Axis**: NLP-extracted tone (using local LLM/phi3) from nurse/physician notes.
- **DHS Output**: A weighted aggregate that triggers "Early Warning" signals 12-24 hours before traditional alarms.

### 3. Architecture (Optimized for Laptop/No GPU)
- **Processing Engine**: `spaCy` + `phi3:mini` (Ollama as an inference microservice).
- **Predictive Modeling**: `LightGBM` or `RandomForest` for trend forecasting (CPU efficient).
- **Data Architecture**: Synthetic Clinical History Generator following FHIR standards.
- **Interface**: High-Fidelity Dashboard using **Glassmorphism design** (Medical Grade).

### 4. Key Performance Indicators (For Judges)
- **Zero-Latency Inference**: Sub-second scoring on a standard CPU.
- **Privacy-Native**: Data stays on-device, satisfying strict healthcare compliance.
- **Actionable Insights**: Automatic generation of "Clinical Summary" for shift handovers.
