"""
NLP model service.

Provides:
- Intent classification (custom-trained TF-IDF + LogReg)
- Entity extraction (recipient, subject, body keywords)
- Email generation via OpenAI GPT-3.5-turbo (falls back to templates)
"""
from __future__ import annotations

import re
import logging
from typing import Any

from backend.config import settings
from backend.training.train import load_pipeline

log = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Intent classifier (loaded once at module import time)
# ──────────────────────────────────────────────────────────────────────────────
_pipeline = None


def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = load_pipeline()
    return _pipeline


def predict_intent(text: str) -> tuple[str, float]:
    """Return (intent_label, confidence_score)."""
    pipe = _get_pipeline()
    proba = pipe.predict_proba([text])[0]
    idx = int(proba.argmax())
    intent = pipe.classes_[idx]
    confidence = float(proba[idx])
    return intent, confidence


# ──────────────────────────────────────────────────────────────────────────────
# Entity extraction
# ──────────────────────────────────────────────────────────────────────────────
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}")
_TO_PATTERNS = [
    re.compile(r"(?:to|for|at)\s+([\w\s]+?)(?:\s+about|\s+regarding|\s*$)", re.I),
    re.compile(r"email\s+([\w\s]+?)(?:\s+about|\s+regarding|\s*$)", re.I),
]
_ABOUT_PATTERNS = [
    re.compile(r"about\s+(.+?)(?:\s+regarding|\s*$)", re.I),
    re.compile(r"regarding\s+(.+?)(?:\s*$)", re.I),
    re.compile(r"subject[:\s]+(.+?)(?:\s*$)", re.I),
]


def extract_entities(text: str) -> dict[str, str]:
    """Extract email address, recipient name, and subject hint from free text."""
    entities: dict[str, str] = {}

    # Email address
    emails = _EMAIL_RE.findall(text)
    if emails:
        entities["recipient_email"] = emails[0]

    # Recipient name
    for pat in _TO_PATTERNS:
        m = pat.search(text)
        if m:
            entities["recipient_name"] = m.group(1).strip()
            break

    # Subject / about
    for pat in _ABOUT_PATTERNS:
        m = pat.search(text)
        if m:
            entities["subject_hint"] = m.group(1).strip()
            break

    return entities


# ──────────────────────────────────────────────────────────────────────────────
# Email generation
# ──────────────────────────────────────────────────────────────────────────────
_OPENAI_AVAILABLE = False
try:
    from openai import OpenAI

    _openai_client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
    _OPENAI_AVAILABLE = bool(settings.openai_api_key)
except ImportError:
    _openai_client = None

SYSTEM_PROMPT = (
    "You are a professional email assistant for {email}. "
    "You help compose, reply to, and manage emails clearly and professionally. "
    "When generating email content, produce only the email body unless asked otherwise. "
    "Keep responses concise and businesslike unless instructed differently."
)

CONVERSATION_HISTORY: list[dict[str, str]] = []
_MAX_HISTORY = 20


def _call_openai(messages: list[dict[str, str]]) -> str:
    """Call the OpenAI Chat Completions API."""
    if _openai_client is None:
        raise RuntimeError("OpenAI client not initialised")
    response = _openai_client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages,
        temperature=0.7,
        max_tokens=512,
    )
    return response.choices[0].message.content.strip()


def _template_response(intent: str, entities: dict[str, str], user_text: str) -> str:
    """Fallback template-based response when OpenAI is unavailable."""
    recipient = entities.get("recipient_email") or entities.get("recipient_name") or "the recipient"
    subject = entities.get("subject_hint") or "your request"

    templates: dict[str, str] = {
        "compose": (
            f"Subject: {subject.capitalize()}\n\n"
            f"Dear {recipient},\n\n"
            "I hope this message finds you well. I am writing to discuss "
            f"{subject}. Please let me know a convenient time to connect.\n\n"
            f"Best regards,\n{settings.email_address}"
        ),
        "reply": (
            f"Dear {recipient},\n\n"
            "Thank you for your email. I have reviewed the details and will "
            "respond accordingly.\n\n"
            f"Best regards,\n{settings.email_address}"
        ),
        "forward": f"Please find the forwarded message below.\n\n--- Forwarded by {settings.email_address} ---",
        "draft": f"[DRAFT SAVED]\n\nDear {recipient},\n\n(Draft regarding {subject})\n\n",
        "read_inbox": (
            "📥 To read your inbox, please use the CLI:\n"
            "    email-assistant inbox\n"
            "or visit the Inbox panel in the web frontend.\n"
            "(Gmail credentials required.)"
        ),
        "search": (
            "🔍 To search emails, please use:\n"
            "    email-assistant search \"your query\"\n"
            "or use the search bar in the web frontend.\n"
            "(Gmail credentials required.)"
        ),
        "delete": (
            "🗑️  To delete an email, please use the Inbox panel in the web frontend\n"
            "or the CLI after reading your inbox.\n"
            "(Gmail credentials required.)"
        ),
        "greet": "Hello! I'm your NLP Email Assistant. How can I help you today?",
        "help": (
            "Here's what I can do:\n"
            "  📧 compose  – Write a new email\n"
            "  ↩️  reply    – Reply to an email\n"
            "  ➡️  forward  – Forward an email\n"
            "  📥 read     – Read your inbox\n"
            "  🔍 search   – Search emails\n"
            "  🗑️  delete   – Delete an email\n"
            "  💾 draft    – Save as draft\n"
            "  🎤 voice    – Use voice input (CLI only)"
        ),
        "unknown": (
            "I specialise in email tasks. Try asking me to compose, reply, "
            "read, search, or forward an email."
        ),
    }
    return templates.get(intent, templates["unknown"])


def chat(user_text: str) -> dict[str, Any]:
    """
    Process a user utterance and return a response dict with keys:
      - intent: str
      - confidence: float
      - entities: dict
      - response: str
    """
    intent, confidence = predict_intent(user_text)
    entities = extract_entities(user_text)

    if _OPENAI_AVAILABLE:
        system_msg = SYSTEM_PROMPT.format(email=settings.email_address)
        CONVERSATION_HISTORY.append({"role": "user", "content": user_text})

        messages = [{"role": "system", "content": system_msg}] + CONVERSATION_HISTORY[
            -_MAX_HISTORY:
        ]
        try:
            response_text = _call_openai(messages)
            CONVERSATION_HISTORY.append({"role": "assistant", "content": response_text})
        except Exception as exc:
            log.warning("OpenAI call failed (%s) — using template fallback", exc)
            response_text = _template_response(intent, entities, user_text)
    else:
        response_text = _template_response(intent, entities, user_text)

    return {
        "intent": intent,
        "confidence": round(confidence, 4),
        "entities": entities,
        "response": response_text,
    }


def reset_conversation() -> None:
    """Clear the in-memory conversation history."""
    CONVERSATION_HISTORY.clear()
