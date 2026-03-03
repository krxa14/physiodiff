"""
Risk Modeling — 12h/24h Forecast using RandomForest + statistical trend detection.

Input: 7-day history of DHS scores, NEWS2 scores, and sentiment scores.
Output: RiskForecast with trend direction, predicted DHS, and recommendation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Any

import numpy as np

try:
    from sklearn.ensemble import RandomForestRegressor
    _SKLEARN_AVAILABLE = True
except ImportError:
    _SKLEARN_AVAILABLE = False

# Minimum records needed to train RandomForest
_RF_MIN_RECORDS = 5
_RF_N_ESTIMATORS = 50  # CPU-efficient for 7-record window


@dataclass
class RiskForecast:
    patient_id: str
    trend_direction: str          # 'RISING', 'FALLING', 'STABLE'
    forecast_12h: float           # predicted DHS at +12h
    forecast_24h: float           # predicted DHS at +24h
    confidence: float             # 0.0 to 1.0
    recommendation: str
    hidden_deterioration_warning: bool = False


def _compute_trend(values: List[float]) -> tuple[str, float]:
    """
    Compute trend direction from a time series using linear regression slope.
    Returns (direction, slope).
    """
    if len(values) < 2:
        return "STABLE", 0.0

    x = np.arange(len(values), dtype=float)
    y = np.array(values, dtype=float)

    # Linear regression slope
    x_mean, y_mean = x.mean(), y.mean()
    denom = np.sum((x - x_mean) ** 2)
    if denom == 0:
        return "STABLE", 0.0

    slope = np.sum((x - x_mean) * (y - y_mean)) / denom

    # Threshold: 0.01 DHS units per day
    if slope > 0.01:
        return "RISING", slope
    elif slope < -0.01:
        return "FALLING", slope
    else:
        return "STABLE", slope


def _rf_forecast(
    dhs_history: List[float],
    steps_ahead: int = 1,
) -> tuple[float, float]:
    """
    Use RandomForest to predict future DHS values.
    Returns (predicted_value, confidence).
    Falls back to linear extrapolation if insufficient data or sklearn unavailable.
    """
    n = len(dhs_history)

    if n < 2:
        return dhs_history[-1], 0.3

    # Linear extrapolation (always computed as fallback)
    x = np.arange(n, dtype=float)
    y = np.array(dhs_history, dtype=float)
    x_mean, y_mean = x.mean(), y.mean()
    denom = np.sum((x - x_mean) ** 2)
    if denom > 0:
        slope = np.sum((x - x_mean) * (y - y_mean)) / denom
    else:
        slope = 0.0
    linear_pred = max(0.0, min(1.0, dhs_history[-1] + slope * steps_ahead))

    if not _SKLEARN_AVAILABLE or n < _RF_MIN_RECORDS:
        # Low confidence for statistical fallback
        confidence = 0.3 if n < 2 else min(0.5, 0.2 + n * 0.05)
        return linear_pred, confidence

    # Build supervised dataset: windows of size (n-1) predict next value
    window_size = min(4, n - 1)
    X, y_train = [], []
    for i in range(n - window_size):
        X.append(dhs_history[i: i + window_size])
        y_train.append(dhs_history[i + window_size])

    if len(X) < 2:
        return linear_pred, 0.4

    rf = RandomForestRegressor(n_estimators=_RF_N_ESTIMATORS, random_state=42)
    rf.fit(X, y_train)

    # Predict using last window
    last_window = dhs_history[-window_size:]
    pred = float(rf.predict([last_window])[0])
    pred = max(0.0, min(1.0, pred))
    confidence = min(0.85, 0.5 + len(X) * 0.05)

    return pred, confidence


def forecast_risk(
    history: List[Dict[str, Any]],
    patient_id: str = "unknown",
) -> RiskForecast:
    """
    Generate a risk forecast from patient history.

    Args:
        history: List of dicts with keys: dhs_score, news2_score, sentiment_score.
                 Should be ordered oldest → newest. At least 1 record required.
        patient_id: Patient identifier for the result.

    Returns:
        RiskForecast dataclass.
    """
    if not history:
        return RiskForecast(
            patient_id=patient_id,
            trend_direction="STABLE",
            forecast_12h=0.0,
            forecast_24h=0.0,
            confidence=0.0,
            recommendation="Insufficient data for forecast.",
        )

    dhs_values = [float(r.get("dhs_score", 0.0)) for r in history]
    news2_values = [float(r.get("news2_score", 0)) for r in history]
    sentiment_values = [float(r.get("sentiment_score", 0.0)) for r in history]

    # Single record: graceful fallback
    if len(history) == 1:
        return RiskForecast(
            patient_id=patient_id,
            trend_direction="STABLE",
            forecast_12h=dhs_values[0],
            forecast_24h=dhs_values[0],
            confidence=0.2,
            recommendation="Only one historical record available. Monitoring required.",
        )

    trend_direction, slope = _compute_trend(dhs_values)
    forecast_12h, confidence_12h = _rf_forecast(dhs_values, steps_ahead=1)
    forecast_24h, confidence_24h = _rf_forecast(dhs_values, steps_ahead=2)
    confidence = round((confidence_12h + confidence_24h) / 2, 3)

    # Hidden deterioration: stable/low NEWS2 but declining sentiment
    recent_news2 = np.mean(news2_values[-3:]) if len(news2_values) >= 3 else news2_values[-1]
    recent_sentiment = np.mean(sentiment_values[-3:]) if len(sentiment_values) >= 3 else sentiment_values[-1]
    sentiment_slope = _compute_trend(sentiment_values[-4:] if len(sentiment_values) >= 4 else sentiment_values)[1]

    hidden_deterioration_warning = (
        recent_news2 < 3
        and recent_sentiment < -0.3
        and sentiment_slope < 0
    )

    # Build recommendation
    if trend_direction == "RISING":
        recommendation = "DHS score is rising. Escalate monitoring frequency."
    elif trend_direction == "FALLING":
        recommendation = "DHS score is improving. Continue current management."
    else:
        recommendation = "DHS score is stable. Routine monitoring."

    if hidden_deterioration_warning:
        recommendation = (
            "Hidden deterioration detected: stable vital signs but declining clinical note sentiment. "
            "Recommend urgent clinical review — NEWS2 score may understate risk."
        )

    return RiskForecast(
        patient_id=patient_id,
        trend_direction=trend_direction,
        forecast_12h=round(forecast_12h, 4),
        forecast_24h=round(forecast_24h, 4),
        confidence=confidence,
        recommendation=recommendation,
        hidden_deterioration_warning=hidden_deterioration_warning,
    )
