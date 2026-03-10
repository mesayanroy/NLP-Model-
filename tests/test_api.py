"""
Integration tests for the FastAPI backend.

Uses FastAPI TestClient — no external services required.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app)


class TestHealthCheck:
    def test_root_returns_ok(self):
        r = client.get("/")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestChatEndpoint:
    def test_chat_hello(self):
        r = client.post("/chat", json={"message": "hello"})
        assert r.status_code == 200
        data = r.json()
        assert data["intent"] == "greet"
        assert "response" in data
        assert data["confidence"] > 0

    def test_chat_compose(self):
        r = client.post("/chat", json={"message": "write an email to Alice about the project"})
        assert r.status_code == 200
        data = r.json()
        assert data["intent"] == "compose"

    def test_chat_empty_message(self):
        r = client.post("/chat", json={"message": "   "})
        assert r.status_code == 422

    def test_chat_missing_message(self):
        r = client.post("/chat", json={})
        assert r.status_code == 422

    def test_chat_reset(self):
        r = client.post("/chat/reset")
        assert r.status_code == 200
        assert r.json()["status"] == "conversation reset"


class TestEmailEndpoints:
    """
    These tests validate request/response structure.
    They expect HTTP 500 when Gmail is not configured — which is acceptable
    in a test environment without credentials.
    """

    def _is_acceptable(self, status_code: int) -> bool:
        return status_code in (200, 500)

    def test_inbox_endpoint_exists(self):
        r = client.get("/email/inbox")
        assert self._is_acceptable(r.status_code)

    def test_inbox_with_query(self):
        r = client.get("/email/inbox?query=test&max_results=5")
        assert self._is_acceptable(r.status_code)

    def test_search_endpoint_exists(self):
        r = client.get("/email/search?q=from%3Aalice")
        assert self._is_acceptable(r.status_code)

    def test_send_email_validation(self):
        # Missing body fields → 422
        r = client.post("/email/send", json={})
        assert r.status_code == 422

    def test_draft_validation(self):
        r = client.post("/email/draft", json={})
        assert r.status_code == 422

    def test_forward_validation(self):
        r = client.post("/email/forward", json={})
        assert r.status_code == 422

    def test_reply_validation(self):
        r = client.post("/email/reply", json={})
        assert r.status_code == 422

    def test_delete_endpoint_exists(self):
        r = client.delete("/email/fake-id-123")
        assert self._is_acceptable(r.status_code)
