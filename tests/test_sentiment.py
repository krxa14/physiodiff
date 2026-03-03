"""Tests for sentiment analysis heuristic."""
import pytest
from app.services.sentiment_analysis import analyze_sentiment, _heuristic_sentiment


class TestHeuristicSentiment:
    def test_positive_note_scores_above_0_3(self):
        result = analyze_sentiment("Patient alert and oriented, tolerating diet well", use_llm=False)
        assert result.score >= 0.3

    def test_negative_note_scores_below_minus_0_3(self):
        result = analyze_sentiment("Patient deteriorating, worsening condition", use_llm=False)
        assert result.score <= -0.3

    def test_empty_string_returns_0(self):
        result = analyze_sentiment("", use_llm=False)
        assert result.score == 0.0

    def test_whitespace_only_returns_0(self):
        result = analyze_sentiment("   ", use_llm=False)
        assert result.score == 0.0

    def test_clinical_deterioration_below_minus_0_5(self):
        result = analyze_sentiment("Confused, agitated, laboured breathing", use_llm=False)
        assert result.score <= -0.5

    def test_clinical_improvement_above_0_4(self):
        result = analyze_sentiment("Alert, oriented, tolerating diet well", use_llm=False)
        assert result.score >= 0.4

    def test_use_llm_false_uses_heuristic(self):
        result = analyze_sentiment("Patient stable", use_llm=False)
        assert result.method == "heuristic"

    def test_multiple_negative_keywords_compound(self):
        result = analyze_sentiment(
            "Patient confused, agitated, distressed, worsening. Diaphoretic.", use_llm=False
        )
        assert result.score < -0.5

    def test_multiple_positive_keywords_compound(self):
        result = analyze_sentiment(
            "Alert, oriented, stable, comfortable, tolerating diet. Improving.", use_llm=False
        )
        assert result.score > 0.3

    def test_score_clamped_to_negative_one(self):
        very_negative = " ".join([
            "confused agitated distressed laboured deteriorating declining worsening",
            "diaphoretic combative disoriented unresponsive anxious clammy",
        ])
        result = analyze_sentiment(very_negative, use_llm=False)
        assert result.score >= -1.0

    def test_score_clamped_to_positive_one(self):
        very_positive = " ".join([
            "alert oriented tolerating improving stable comfortable",
            "well mobilising eating responding cooperating appropriate",
        ])
        result = analyze_sentiment(very_positive, use_llm=False)
        assert result.score <= 1.0

    def test_result_has_method_field(self):
        result = analyze_sentiment("Normal observation", use_llm=False)
        assert hasattr(result, "method")
        assert result.method == "heuristic"

    def test_result_has_confidence_field(self):
        result = analyze_sentiment("Patient alert and oriented", use_llm=False)
        assert hasattr(result, "confidence")
        assert 0.0 <= result.confidence <= 1.0

    def test_acutely_distressed_diaphoretic(self):
        result = analyze_sentiment("Acutely distressed, diaphoretic", use_llm=False)
        assert result.score < -0.3

    def test_short_of_breath(self):
        result = analyze_sentiment("Short of breath at rest, non-responsive", use_llm=False)
        assert result.score < -0.4
