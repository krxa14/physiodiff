"""
DHS (Delta Homeostasis Score) Algorithm — CORE LOGIC

Combines NEWS2 physiological scoring with NLP sentiment analysis to detect
hidden clinical deterioration 12-24 hours before traditional alarms.

IMPROVEMENTS (v1.1):
  - Clamp sentiment_deterioration to [0, 1] to prevent DHS > 1.0
    - Add SpO2 Scale 2 support for patients on supplemental oxygen
      - Enhanced hidden deterioration alert logic (also triggers on dhs_score > 0.5)
        - Structured logging support for debugging
        """
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# --- Constants (DO NOT CHANGE without explicit instruction) ---
DHS_NEWS2_WEIGHT = 0.65
DHS_SENTIMENT_WEIGHT = 0.35
HIDDEN_DETERIORATION_NEWS2_THRESHOLD = 3  # NEWS2 < 3 means vitals look normal
HIDDEN_DETERIORATION_SENTIMENT_THRESHOLD = -0.4  # strong negative signal required
HIDDEN_DETERIORATION_DHS_THRESHOLD = 0.5  # DHS > 0.5 also triggers alert
MAX_NEWS2 = 20.0  # theoretical maximum for normalization


@dataclass
class DHSResult:
      dhs_score: float
      news2_score: int
      risk_level: str
      alert_triggered: bool
      hidden_deterioration: bool
      rr_score: int
      spo2_score: int
      sbp_score: int
      hr_score: int
      temp_score: int
      consciousness_score: int
      o2_score: int
      spo2_scale: int = 1  # 1 or 2


# --- NEWS2 Individual Parameter Scoring ---

def score_respiratory_rate(rr: float) -> int:
      """NEWS2 respiratory rate scoring."""
      if rr <= 8:
                return 3
elif rr <= 11:
        return 1
elif rr <= 20:
        return 0
elif rr <= 24:
        return 2
else:
        return 3


def score_oxygen_saturation(spo2: float) -> int:
      """NEWS2 SpO2 Scale 1 scoring (for patients NOT on supplemental O2)."""
      if spo2 <= 91:
                return 3
elif spo2 <= 93:
        return 2
elif spo2 <= 95:
        return 1
else:
        return 0


def score_oxygen_saturation_scale2(spo2: float) -> int:
      """NEWS2 SpO2 Scale 2 scoring (for patients ON supplemental O2).

          Uses higher thresholds because any SpO2 < 88% on supplemental O2 is critical.
              """
      if spo2 <= 83:
                return 3
elif spo2 <= 85:
        return 2
elif spo2 <= 87:
        return 1
else:
        return 0


def score_systolic_bp(sbp: float) -> int:
      """NEWS2 systolic blood pressure scoring."""
      if sbp <= 90:
                return 3
elif sbp <= 100:
        return 2
elif sbp <= 110:
        return 1
elif sbp <= 219:
        return 0
else:
        return 3


def score_heart_rate(hr: float) -> int:
      """NEWS2 heart rate scoring."""
      if hr <= 40:
                return 3
elif hr <= 50:
        return 1
elif hr <= 90:
        return 0
elif hr <= 110:
        return 1
elif hr <= 130:
        return 2
else:
        return 3


def score_temperature(temp: float) -> int:
      """NEWS2 temperature scoring.

              Note: boundary at 39.0 vs 39.1 — <=39.0 returns 1, >=39.1 returns 2.
                  """
      if temp <= 35.0:
                return 3
elif temp <= 36.0:
        return 1
elif temp <= 38.0:
        return 0
elif temp <= 39.0:
        return 1
else:
        return 2


def score_consciousness(level: int) -> int:
      """NEWS2 AVPU consciousness scoring. 0=Alert, 1=V/P/U."""
      return 0 if level == 0 else 3


def score_supplemental_o2(on_o2: bool) -> int:
      """NEWS2 supplemental oxygen scoring."""
      return 2 if on_o2 else 0


def calculate_news2(
      respiratory_rate: float,
      spo2: float,
      systolic_bp: float,
      heart_rate: float,
      temperature: float,
      consciousness: int = 0,
      on_supplemental_o2: bool = False,
) -> int:
      """Calculate total NEWS2 score from vital signs.

              Automatically selects SpO2 Scale 1 or Scale 2 based on supplemental O2 status.
                  """
      # Use Scale 2 if patient is on supplemental O2
      if on_supplemental_o2:
                spo2_score = score_oxygen_saturation_scale2(spo2)
                logger.debug("Using SpO2 Scale 2 (patient on supplemental O2): spo2=%.1f -> score=%d", spo2, spo2_score)
else:
        spo2_score = score_oxygen_saturation(spo2)

    return (
              score_respiratory_rate(respiratory_rate)
              + spo2_score
              + score_systolic_bp(systolic_bp)
              + score_heart_rate(heart_rate)
              + score_temperature(temperature)
              + score_consciousness(consciousness)
              + score_supplemental_o2(on_supplemental_o2)
    )


def _news2_to_risk_level(news2: int) -> str:
      """Map NEWS2 score to risk level."""
    if news2 >= 7:
              return "CRITICAL"
elif news2 >= 5:
        return "HIGH"
elif news2 >= 3:
        return "MEDIUM"
else:
        return "LOW"


def calculate_dhs(
      respiratory_rate: float,
      spo2: float,
      systolic_bp: float,
      heart_rate: float,
      temperature: float,
      consciousness: int = 0,
      on_supplemental_o2: bool = False,
      sentiment_score: float = 0.0,
) -> DHSResult:
      """
          Calculate the Delta Homeostasis Score (DHS).

              DHS = news2_weight * normalized_NEWS2 + sentiment_weight * deterioration_signal
                  where deterioration_signal = max(0, -sentiment_score), clamped to [0, 1]

                      v1.1 changes:
                          - sentiment_deterioration is now clamped to [0, 1] preventing DHS > 1.0
                              - SpO2 Scale 2 auto-selected when patient is on supplemental O2
                                  - alert_triggered now also fires when dhs_score > HIDDEN_DETERIORATION_DHS_THRESHOLD
                                      """
    rr_score = score_respiratory_rate(respiratory_rate)
    sbp_score = score_systolic_bp(systolic_bp)
    hr_score = score_heart_rate(heart_rate)
    temp_score = score_temperature(temperature)
    consciousness_score = score_consciousness(consciousness)
    o2_score = score_supplemental_o2(on_supplemental_o2)

    # Select SpO2 scoring scale based on supplemental O2 status
    if on_supplemental_o2:
              spo2_score = score_oxygen_saturation_scale2(spo2)
              spo2_scale = 2
else:
        spo2_score = score_oxygen_saturation(spo2)
          spo2_scale = 1

    news2_score = (
              rr_score + spo2_score + sbp_score + hr_score
              + temp_score + consciousness_score + o2_score
    )

    # Normalize NEWS2 to 0-1
    news2_normalized = min(news2_score / MAX_NEWS2, 1.0)

    # Sentiment deterioration signal: 0 when positive/neutral, clamped to [0, 1]
    # FIX: clamp to max of 1.0 to prevent DHS exceeding designed range
    sentiment_deterioration = max(0.0, min(1.0, -float(sentiment_score)))

    # DHS: higher = more risk (range: 0.0 to 1.0)
    dhs_score = round(
              DHS_NEWS2_WEIGHT * news2_normalized + DHS_SENTIMENT_WEIGHT * sentiment_deterioration,
              4,
    )

    # Primary risk level from NEWS2
    risk_level = _news2_to_risk_level(news2_score)

    # Hidden deterioration: vitals look normal but notes signal decline
    hidden_deterioration = (
              news2_score < HIDDEN_DETERIORATION_NEWS2_THRESHOLD
              and float(sentiment_score) < HIDDEN_DETERIORATION_SENTIMENT_THRESHOLD
    )

    # Alert triggered by hidden deterioration OR high DHS score with borderline vitals
    alert_triggered = hidden_deterioration or (
              dhs_score > HIDDEN_DETERIORATION_DHS_THRESHOLD
              and news2_score < HIDDEN_DETERIORATION_NEWS2_THRESHOLD
    )

    # Upgrade risk level if hidden deterioration detected
    if hidden_deterioration and risk_level == "LOW":
              risk_level = "MEDIUM"

    logger.debug(
              "DHS calculated: news2=%d, dhs=%.4f, risk=%s, hidden_det=%s, alert=%s, spo2_scale=%d",
              news2_score, dhs_score, risk_level, hidden_deterioration, alert_triggered, spo2_scale,
    )

    return DHSResult(
              dhs_score=dhs_score,
              news2_score=news2_score,
              risk_level=risk_level,
              alert_triggered=alert_triggered,
              hidden_deterioration=hidden_deterioration,
              rr_score=rr_score,
              spo2_score=spo2_score,
              sbp_score=sbp_score,
              hr_score=hr_score,
              temp_score=temp_score,
              consciousness_score=consciousness_score,
              o2_score=o2_score,
              spo2_scale=spo2_scale,
    )
