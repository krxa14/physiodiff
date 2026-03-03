"""
Synthetic patient and vital signs data generator.

Generates realistic clinical data with varied risk profiles to produce
a credible risk distribution across LOW / MEDIUM / HIGH / CRITICAL levels.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import List, Dict, Any

import numpy as np

from app.models.dhs_algorithm import calculate_dhs
from app.sentiment_analysis import analyze_sentiment

WARDS = ["Medical Ward A", "Medical Ward B", "Surgical Ward", "HDU", "CCU", "Cardiology", "Respiratory"]

FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda",
    "William", "Barbara", "David", "Elizabeth", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Charles", "Karen", "Emma", "Oliver", "Sophia", "Liam",
    "Olivia", "Noah", "Ava", "Elijah", "Charlotte", "Lucas",
]
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Wilson", "Taylor", "Anderson", "Thomas", "Jackson", "White", "Harris", "Martin",
    "Thompson", "Robinson", "Clark", "Lewis", "Walker", "Allen", "Young", "King",
    "Scott", "Green", "Baker", "Adams", "Nelson", "Mitchell",
]

# Clinical note templates indexed by sentiment profile
_NOTES_POSITIVE = [
    "Patient alert and oriented, tolerating diet well. Vitals stable overnight.",
    "Good colour, cooperative and comfortable. Mobilising with physiotherapy.",
    "Improving steadily. Eating and drinking satisfactorily. Afebrile.",
    "Oriented to time and place. Engaging with staff. No complaints.",
    "Responding well to treatment. Appropriate affect. Pain controlled.",
    "Up and about. Walking short distances. Satisfactory progress.",
    "Stable and comfortable. Normotensive. Clear chest on auscultation.",
    "Good appetite. Bowels open. No new concerns. Discharge planning started.",
]

_NOTES_NEUTRAL = [
    "Patient resting comfortably. Observations within normal limits.",
    "Vitals reviewed. No acute concerns noted at this time.",
    "Routine observations completed. Continuing current management.",
    "Patient reviewed by team. Plan unchanged. Monitor closely.",
    "Overnight observations stable. Further review in morning.",
    "No significant change since last review. Continue monitoring.",
]

_NOTES_NEGATIVE = [
    "Confused and agitated. Laboured breathing noted. Urgent review requested.",
    "Patient appears distressed. Decreased urine output. Diaphoretic.",
    "Worsening mental status. Disoriented to time and place. Combative.",
    "Acutely unwell. Declining observations. High DHS — escalate to registrar.",
    "Short of breath at rest. Non-responsive to verbal stimuli. Emergency call placed.",
    "Deteriorating clinical picture. Respiratory distress. Anxious and restless.",
    "Confused. Agitated. Poor oral intake. Weaker than previous assessment.",
    "Laboured breathing, diaphoretic, acute distress. Nurse concerned.",
]


def _pick_note(sentiment_profile: str) -> tuple[str, float]:
    """Return (note_text, expected_sentiment_score)."""
    if sentiment_profile == "positive":
        note = random.choice(_NOTES_POSITIVE)
        score = random.uniform(0.4, 0.8)
    elif sentiment_profile == "negative":
        note = random.choice(_NOTES_NEGATIVE)
        score = random.uniform(-0.8, -0.45)
    else:
        note = random.choice(_NOTES_NEUTRAL)
        score = random.uniform(-0.15, 0.15)
    return note, round(score, 4)


def _vitals_for_profile(profile: str, rng: random.Random) -> Dict[str, float]:
    """Generate realistic vital signs for a given risk profile."""
    if profile == "critical":
        return {
            "respiratory_rate": rng.uniform(24, 35),
            "spo2": rng.uniform(85, 92),
            "systolic_bp": rng.uniform(75, 100),
            "heart_rate": rng.uniform(115, 145),
            "temperature": rng.uniform(38.5, 40.0),
            "consciousness": rng.choice([0, 1]),
            "on_supplemental_o2": True,
        }
    elif profile == "high":
        return {
            "respiratory_rate": rng.uniform(22, 28),
            "spo2": rng.uniform(91, 94),
            "systolic_bp": rng.uniform(92, 112),
            "heart_rate": rng.uniform(105, 130),
            "temperature": rng.uniform(38.0, 39.5),
            "consciousness": 0,
            "on_supplemental_o2": rng.choice([True, False]),
        }
    elif profile == "medium":
        return {
            "respiratory_rate": rng.uniform(18, 23),
            "spo2": rng.uniform(93, 96),
            "systolic_bp": rng.uniform(100, 115),
            "heart_rate": rng.uniform(90, 112),
            "temperature": rng.uniform(37.5, 38.5),
            "consciousness": 0,
            "on_supplemental_o2": False,
        }
    elif profile == "hidden":
        # Hidden deterioration: vitals look normal, but notes are negative
        return {
            "respiratory_rate": rng.uniform(14, 19),
            "spo2": rng.uniform(95, 99),
            "systolic_bp": rng.uniform(112, 130),
            "heart_rate": rng.uniform(60, 90),
            "temperature": rng.uniform(36.5, 37.5),
            "consciousness": 0,
            "on_supplemental_o2": False,
        }
    else:  # low
        return {
            "respiratory_rate": rng.uniform(12, 18),
            "spo2": rng.uniform(96, 100),
            "systolic_bp": rng.uniform(110, 140),
            "heart_rate": rng.uniform(55, 88),
            "temperature": rng.uniform(36.2, 37.5),
            "consciousness": 0,
            "on_supplemental_o2": False,
        }


def _sentiment_profile_for(risk_profile: str, rng: random.Random) -> str:
    """Choose clinical note sentiment profile based on risk profile."""
    if risk_profile == "critical":
        return rng.choices(["negative", "neutral"], weights=[0.9, 0.1])[0]
    elif risk_profile == "high":
        return rng.choices(["negative", "neutral"], weights=[0.6, 0.4])[0]
    elif risk_profile == "hidden":
        return "negative"  # key for hidden deterioration
    elif risk_profile == "medium":
        return rng.choices(["negative", "neutral", "positive"], weights=[0.3, 0.5, 0.2])[0]
    else:
        return rng.choices(["positive", "neutral"], weights=[0.7, 0.3])[0]


def generate_patients(n_patients: int = 50, seed: int = 42) -> List[Dict[str, Any]]:
    """
    Generate a list of synthetic patients with 7-day vitals history.

    Each patient has:
    - id, name, ward, date_of_birth, admission_date
    - vitals_history: list of 7 records
    """
    rng = random.Random(seed)
    np_rng = np.random.default_rng(seed)

    # Risk profile distribution across patients
    profiles = (
        ["low"] * 20
        + ["medium"] * 12
        + ["hidden"] * 8
        + ["high"] * 7
        + ["critical"] * 3
    )
    if len(profiles) < n_patients:
        profiles += ["low"] * (n_patients - len(profiles))
    profiles = profiles[:n_patients]
    rng.shuffle(profiles)

    patients = []
    used_names: set[str] = set()

    for i in range(n_patients):
        # Unique name
        for _ in range(100):
            name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
            if name not in used_names:
                used_names.add(name)
                break

        age = rng.randint(35, 90)
        dob = (datetime.now() - timedelta(days=age * 365)).strftime("%Y-%m-%d")
        admission_date = (datetime.now() - timedelta(days=rng.randint(1, 14))).strftime("%Y-%m-%d")
        ward = rng.choice(WARDS)
        profile = profiles[i]

        # Generate 7-day history
        history = []
        base_time = datetime.now() - timedelta(days=6)

        for day in range(7):
            # Allow some variation in profile across days
            day_profile = profile
            if profile in ("low", "medium") and day >= 5:
                # Some stable patients start to deteriorate at end
                day_profile = rng.choices(
                    [profile, "hidden"],
                    weights=[0.85, 0.15]
                )[0]

            vitals = _vitals_for_profile(day_profile, rng)
            sent_profile = _sentiment_profile_for(day_profile, rng)
            note, sent_score = _pick_note(sent_profile)

            dhs_result = calculate_dhs(
                respiratory_rate=vitals["respiratory_rate"],
                spo2=vitals["spo2"],
                systolic_bp=vitals["systolic_bp"],
                heart_rate=vitals["heart_rate"],
                temperature=vitals["temperature"],
                consciousness=int(vitals["consciousness"]),
                on_supplemental_o2=bool(vitals["on_supplemental_o2"]),
                sentiment_score=sent_score,
            )

            record = {
                "timestamp": (base_time + timedelta(days=day)).isoformat(),
                "respiratory_rate": round(vitals["respiratory_rate"], 1),
                "spo2": round(vitals["spo2"], 1),
                "systolic_bp": round(vitals["systolic_bp"], 0),
                "heart_rate": round(vitals["heart_rate"], 0),
                "temperature": round(vitals["temperature"], 1),
                "consciousness": int(vitals["consciousness"]),
                "on_supplemental_o2": bool(vitals["on_supplemental_o2"]),
                "clinical_note": note,
                "sentiment_score": sent_score,
                "news2_score": dhs_result.news2_score,
                "dhs_score": dhs_result.dhs_score,
                "risk_level": dhs_result.risk_level,
                "alert_triggered": dhs_result.alert_triggered,
            }
            history.append(record)

        # Latest record drives overall patient risk
        latest = history[-1]

        patients.append({
            "id": i + 1,
            "name": name,
            "ward": ward,
            "date_of_birth": dob,
            "admission_date": admission_date,
            "risk_profile": profile,
            "risk_level": latest["risk_level"],
            "dhs_score": latest["dhs_score"],
            "news2_score": latest["news2_score"],
            "alert_triggered": latest["alert_triggered"],
            "vitals_history": history,
        })

    return patients
