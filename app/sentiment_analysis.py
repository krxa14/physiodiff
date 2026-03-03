"""
Sentiment Analysis for clinical notes.

Primary: Ollama phi3:mini via HTTP (optional, requires local Ollama server).
Fallback: Heuristic keyword-based scoring — always used when use_llm=False
          or when Ollama is unavailable.

Score range: -1.0 (severe deterioration) to +1.0 (clearly improving/stable).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

try:
    import requests as _requests
    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False


OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "phi3:mini"
OLLAMA_TIMEOUT = 10  # seconds

# Clinical keyword weights
# Format: (keyword_pattern, score_delta)
_NEGATIVE_KEYWORDS: list[tuple[str, float]] = [
    (r"\bconfused?\b", -0.25),
    (r"\bagitat(ed|ion)\b", -0.25),
    (r"\bdistressed?\b", -0.25),
    (r"\blabour(ed|ing)?\b", -0.25),
    (r"\bdeteriora(ting|tion)\b", -0.30),
    (r"\bdeclining?\b", -0.25),
    (r"\bworsening?\b", -0.25),
    (r"\bstruggling?\b", -0.20),
    (r"\bunresponsive\b", -0.35),
    (r"\baltered\s+(?:mental)?\s*status\b", -0.30),
    (r"\bdiaphoretic\b", -0.25),
    (r"\bclamm(y|iness)\b", -0.20),
    (r"\banxious\b", -0.20),
    (r"\bcombative\b", -0.25),
    (r"\bdisoriented\b", -0.25),
    (r"\btachycardia\b", -0.20),
    (r"\bhypotens(ive|ion)\b", -0.25),
    (r"\bsepsis\b", -0.30),
    (r"\bacute\b", -0.15),
    (r"\bfever(ish)?\b", -0.15),
    (r"\bpain\b", -0.10),
    (r"\bnausea\b", -0.10),
    (r"\bvomit(ing)?\b", -0.15),
    (r"\bweaker?\b", -0.20),
    (r"\bfatigu(ed|e)\b", -0.15),
    (r"\bshort(?:ness)?\s+of\s+breath\b", -0.25),
    (r"\bdyspnoea\b", -0.25),
    (r"\brespiratory\s+distress\b", -0.30),
    (r"\bnon-?responsive\b", -0.35),
]

_POSITIVE_KEYWORDS: list[tuple[str, float]] = [
    (r"\balert\b", +0.20),
    (r"\boriented\b", +0.20),
    (r"\btolerat(ing|ed)\b", +0.20),
    (r"\bimproving?\b", +0.25),
    (r"\bstable\b", +0.20),
    (r"\bcomfort(able|ed)\b", +0.20),
    (r"\bwell\b", +0.15),
    (r"\bmobilis(ing|ed|ation)\b", +0.20),
    (r"\beat(ing)?\b", +0.15),
    (r"\bresponding\b", +0.15),
    (r"\bclear\b", +0.10),
    (r"\bappropriate\b", +0.15),
    (r"\bengaged?\b", +0.15),
    (r"\bcooperat(ive|ing)\b", +0.15),
    (r"\bup\s+and\s+about\b", +0.20),
    (r"\bwalking\b", +0.15),
    (r"\bconversing\b", +0.15),
    (r"\bgood\s+(?:colour|color|appetite|mood)\b", +0.20),
    (r"\bafebrile\b", +0.20),
    (r"\bnormotensi(ve|on)\b", +0.20),
    (r"\bsatisfactory\b", +0.15),
    (r"\bresolving\b", +0.20),
]


@dataclass
class SentimentResult:
    score: float          # -1.0 to +1.0
    method: str           # 'heuristic' or 'ollama'
    confidence: float     # 0.0 to 1.0


def _heuristic_sentiment(text: str) -> SentimentResult:
    """Keyword-based heuristic sentiment for clinical notes."""
    if not text or not text.strip():
        return SentimentResult(score=0.0, method="heuristic", confidence=0.5)

    text_lower = text.lower()
    score = 0.0

    for pattern, delta in _NEGATIVE_KEYWORDS:
        if re.search(pattern, text_lower):
            score += delta

    for pattern, delta in _POSITIVE_KEYWORDS:
        if re.search(pattern, text_lower):
            score += delta

    # Clamp to [-1, 1]
    score = max(-1.0, min(1.0, score))

    # Confidence based on number of keyword matches
    match_count = sum(
        1 for p, _ in _NEGATIVE_KEYWORDS + _POSITIVE_KEYWORDS
        if re.search(p, text_lower)
    )
    confidence = min(0.9, 0.4 + match_count * 0.1)

    return SentimentResult(score=round(score, 4), method="heuristic", confidence=confidence)


def _ollama_sentiment(text: str) -> Optional[SentimentResult]:
    """Query Ollama phi3:mini for sentiment analysis. Returns None on failure."""
    if not _REQUESTS_AVAILABLE:
        return None

    prompt = (
        "You are a clinical sentiment analyzer. "
        "Rate the following clinical note on a scale from -1.0 (severe deterioration) "
        "to +1.0 (clearly improving/stable). "
        "Reply with ONLY a number between -1.0 and 1.0, nothing else.\n\n"
        f"Note: {text}"
    )

    try:
        resp = _requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=OLLAMA_TIMEOUT,
        )
        if resp.status_code == 200:
            raw = resp.json().get("response", "").strip()
            score = float(re.search(r"-?\d+\.?\d*", raw).group())
            score = max(-1.0, min(1.0, score))
            return SentimentResult(score=round(score, 4), method="ollama", confidence=0.8)
    except Exception:
        pass
    return None


def analyze_sentiment(text: str, use_llm: bool = False) -> SentimentResult:
    """
    Analyze clinical note sentiment.

    Args:
        text: Clinical note text.
        use_llm: If True, attempt Ollama phi3:mini first; fall back to heuristic.

    Returns:
        SentimentResult with score (-1 to +1), method, and confidence.
    """
    if use_llm:
        result = _ollama_sentiment(text)
        if result is not None:
            return result
    return _heuristic_sentiment(text)
