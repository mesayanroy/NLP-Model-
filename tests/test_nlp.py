"""
Unit tests for the NLP model and intent classifier.

These tests run without requiring any external API keys or Gmail credentials.
"""
from __future__ import annotations

import pytest
from backend.training.train import build_pipeline, train, load_pipeline
from backend.training.data import TRAINING_SAMPLES, INTENT_LABELS
from backend.nlp_model import predict_intent, extract_entities, chat, reset_conversation


# ──────────────────────────────────────────────────────────────────────────────
# Training data sanity checks
# ──────────────────────────────────────────────────────────────────────────────


class TestTrainingData:
    def test_samples_not_empty(self):
        assert len(TRAINING_SAMPLES) >= 50

    def test_all_intents_in_labels(self):
        sample_intents = {label for _, label in TRAINING_SAMPLES}
        for intent in sample_intents:
            assert intent in INTENT_LABELS, f"Intent '{intent}' not in INTENT_LABELS"

    def test_label_list_complete(self):
        expected = {
            "compose", "reply", "forward", "read_inbox",
            "search", "delete", "draft", "greet", "help", "unknown",
        }
        assert expected.issubset(set(INTENT_LABELS))

    def test_each_sample_is_tuple_of_two_strings(self):
        for item in TRAINING_SAMPLES:
            assert isinstance(item, tuple)
            assert len(item) == 2
            text, label = item
            assert isinstance(text, str) and text
            assert isinstance(label, str) and label


# ──────────────────────────────────────────────────────────────────────────────
# Pipeline training
# ──────────────────────────────────────────────────────────────────────────────


class TestTraining:
    @pytest.fixture(scope="class")
    def trained_pipeline(self):
        """Train the pipeline once and reuse across tests in this class."""
        return train()

    def test_pipeline_has_tfidf_and_clf(self, trained_pipeline):
        assert "tfidf" in trained_pipeline.named_steps
        assert "clf" in trained_pipeline.named_steps

    def test_pipeline_predicts_string(self, trained_pipeline):
        result = trained_pipeline.predict(["write an email to Alice"])
        assert isinstance(result[0], str)

    def test_pipeline_predicts_correct_intent(self, trained_pipeline):
        assert trained_pipeline.predict(["write an email to Bob"])[0] == "compose"
        assert trained_pipeline.predict(["hello"])[0] == "greet"
        assert trained_pipeline.predict(["read my inbox"])[0] == "read_inbox"

    def test_pipeline_predict_proba_sums_to_one(self, trained_pipeline):
        proba = trained_pipeline.predict_proba(["find emails from Alice"])[0]
        assert abs(sum(proba) - 1.0) < 1e-6

    def test_load_pipeline_returns_pipeline(self):
        pipe = load_pipeline()
        assert pipe is not None


# ──────────────────────────────────────────────────────────────────────────────
# Intent prediction
# ──────────────────────────────────────────────────────────────────────────────


class TestPredictIntent:
    def test_returns_tuple(self):
        intent, conf = predict_intent("write an email")
        assert isinstance(intent, str)
        assert 0.0 <= conf <= 1.0

    @pytest.mark.parametrize("text,expected_intent", [
        ("write an email to John about the meeting", "compose"),
        ("reply to the email from Alice", "reply"),
        ("show me my inbox", "read_inbox"),
        ("find emails about the project", "search"),
        ("delete this email", "delete"),
        ("save as draft", "draft"),
        ("forward this to manager", "forward"),
        ("hello", "greet"),
        ("what can you do", "help"),
    ])
    def test_known_intents(self, text, expected_intent):
        intent, conf = predict_intent(text)
        assert intent == expected_intent, (
            f"Expected '{expected_intent}' for '{text}', got '{intent}' (conf={conf:.2f})"
        )

    def test_confidence_between_0_and_1(self):
        _, conf = predict_intent("any random text here")
        assert 0.0 <= conf <= 1.0


# ──────────────────────────────────────────────────────────────────────────────
# Entity extraction
# ──────────────────────────────────────────────────────────────────────────────


class TestExtractEntities:
    def test_extracts_email_address(self):
        entities = extract_entities("send email to alice@example.com about the project")
        assert entities.get("recipient_email") == "alice@example.com"

    def test_extracts_recipient_name(self):
        entities = extract_entities("write an email to John about the meeting")
        assert "recipient_name" in entities

    def test_extracts_subject_hint_about(self):
        entities = extract_entities("write an email about the quarterly report")
        assert "subject_hint" in entities
        assert "quarterly report" in entities["subject_hint"].lower()

    def test_no_entities_from_empty(self):
        entities = extract_entities("")
        assert isinstance(entities, dict)

    def test_no_false_email_detection(self):
        entities = extract_entities("hello, how are you")
        assert "recipient_email" not in entities


# ──────────────────────────────────────────────────────────────────────────────
# Chat function (no OpenAI key — uses template fallback)
# ──────────────────────────────────────────────────────────────────────────────


class TestChat:
    def setup_method(self):
        reset_conversation()

    def test_chat_returns_required_keys(self):
        result = chat("write an email to Bob")
        assert "intent" in result
        assert "confidence" in result
        assert "entities" in result
        assert "response" in result

    def test_chat_response_is_string(self):
        result = chat("hello")
        assert isinstance(result["response"], str)
        assert result["response"]

    def test_chat_greet_intent(self):
        result = chat("hello")
        assert result["intent"] == "greet"

    def test_chat_help_intent(self):
        result = chat("what can you do")
        assert result["intent"] == "help"

    def test_chat_compose_intent(self):
        result = chat("write an email to manager about leave")
        assert result["intent"] == "compose"

    def test_reset_conversation_clears_history(self):
        from backend.nlp_model import CONVERSATION_HISTORY

        chat("hello")
        reset_conversation()
        assert len(CONVERSATION_HISTORY) == 0
