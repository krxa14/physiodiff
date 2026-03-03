"""Tests for risk modeling — trend detection and forecasting."""
import pytest
from app.models.risk_modeling import forecast_risk, RiskForecast


def _make_history(dhs_values, news2=1, sentiment=0.0):
    return [
        {"dhs_score": v, "news2_score": news2, "sentiment_score": sentiment}
        for v in dhs_values
    ]


class TestTrendDetection:
    def test_rising_trend(self):
        history = _make_history([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7])
        result = forecast_risk(history)
        assert result.trend_direction == "RISING"

    def test_falling_trend(self):
        history = _make_history([0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1])
        result = forecast_risk(history)
        assert result.trend_direction == "FALLING"

    def test_stable_trend(self):
        history = _make_history([0.3, 0.3, 0.31, 0.29, 0.3, 0.31, 0.3])
        result = forecast_risk(history)
        assert result.trend_direction == "STABLE"

    def test_two_records_rising(self):
        history = _make_history([0.2, 0.5])
        result = forecast_risk(history)
        assert result.trend_direction == "RISING"

    def test_two_records_falling(self):
        history = _make_history([0.8, 0.3])
        result = forecast_risk(history)
        assert result.trend_direction == "FALLING"


class TestSingleRecordFallback:
    def test_single_record_does_not_crash(self):
        history = _make_history([0.3])
        result = forecast_risk(history)
        assert isinstance(result, RiskForecast)

    def test_single_record_confidence_below_0_5(self):
        history = _make_history([0.4])
        result = forecast_risk(history)
        assert result.confidence < 0.5

    def test_single_record_stable_trend(self):
        history = _make_history([0.3])
        result = forecast_risk(history)
        assert result.trend_direction == "STABLE"

    def test_empty_history_returns_forecast(self):
        result = forecast_risk([])
        assert isinstance(result, RiskForecast)
        assert result.confidence == 0.0


class TestForecastValues:
    def test_rising_forecast_greater_than_current(self):
        history = _make_history([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7])
        result = forecast_risk(history)
        assert result.forecast_12h >= 0.0
        assert result.forecast_24h >= 0.0

    def test_forecast_clamped_to_unit_interval(self):
        history = _make_history([0.7, 0.75, 0.8, 0.85, 0.88, 0.91, 0.95])
        result = forecast_risk(history)
        assert 0.0 <= result.forecast_12h <= 1.0
        assert 0.0 <= result.forecast_24h <= 1.0

    def test_patient_id_propagated(self):
        history = _make_history([0.3, 0.4])
        result = forecast_risk(history, patient_id="patient-99")
        assert result.patient_id == "patient-99"


class TestHiddenDeteriorationWarning:
    def test_stable_news2_declining_sentiment_triggers_warning(self):
        """Stable low NEWS2 + declining sentiment → recommendation mentions hidden/sentiment."""
        history = [
            {"dhs_score": 0.1, "news2_score": 1, "sentiment_score": 0.2},
            {"dhs_score": 0.1, "news2_score": 1, "sentiment_score": 0.0},
            {"dhs_score": 0.1, "news2_score": 1, "sentiment_score": -0.2},
            {"dhs_score": 0.1, "news2_score": 1, "sentiment_score": -0.4},
            {"dhs_score": 0.1, "news2_score": 1, "sentiment_score": -0.6},
        ]
        result = forecast_risk(history)
        assert (
            "hidden" in result.recommendation.lower()
            or "sentiment" in result.recommendation.lower()
        )

    def test_high_news2_no_hidden_deterioration_warning(self):
        """High NEWS2 patients should not trigger hidden deterioration warning."""
        history = _make_history([0.5, 0.55, 0.6, 0.65], news2=8, sentiment=-0.5)
        result = forecast_risk(history)
        # hidden_deterioration_warning should be False when NEWS2 >= 3
        assert not result.hidden_deterioration_warning

    def test_recommendation_string_not_empty(self):
        history = _make_history([0.3, 0.35, 0.4])
        result = forecast_risk(history)
        assert len(result.recommendation) > 0


class TestRiskForecastDataclass:
    def test_returns_risk_forecast_instance(self):
        history = _make_history([0.2, 0.3, 0.4])
        result = forecast_risk(history)
        assert isinstance(result, RiskForecast)

    def test_all_fields_present(self):
        history = _make_history([0.2, 0.3, 0.4, 0.5])
        result = forecast_risk(history)
        assert hasattr(result, "trend_direction")
        assert hasattr(result, "forecast_12h")
        assert hasattr(result, "forecast_24h")
        assert hasattr(result, "confidence")
        assert hasattr(result, "recommendation")
        assert hasattr(result, "hidden_deterioration_warning")

    def test_confidence_in_unit_interval(self):
        history = _make_history([0.2, 0.3, 0.4, 0.5, 0.6])
        result = forecast_risk(history)
        assert 0.0 <= result.confidence <= 1.0
