"""
Gmail service using the Google People / Gmail REST API.

Authentication flow:
  1. First run: opens browser for OAuth2 consent and saves token.json.
  2. Subsequent runs: refreshes token automatically.

Scopes required:
  - https://www.googleapis.com/auth/gmail.modify
"""
from __future__ import annotations

import base64
import email as _email_lib
import json
import logging
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

from backend.config import settings

log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.readonly",
]

TOKEN_FILE = Path("token.json")
_service = None  # cached Gmail API service


# ──────────────────────────────────────────────────────────────────────────────
# Authentication
# ──────────────────────────────────────────────────────────────────────────────


def _build_service():
    """Build and return an authenticated Gmail API service."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError(
            "Google API libraries not installed. Run: pip install google-api-python-client "
            "google-auth-oauthlib google-auth-httplib2"
        ) from exc

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            credentials_file = settings.google_credentials_file
            if not Path(credentials_file).exists():
                raise FileNotFoundError(
                    f"Google credentials file not found: {credentials_file}\n"
                    "Download it from https://console.cloud.google.com → "
                    "APIs & Services → Credentials"
                )
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
            creds = flow.run_local_server(port=0)

        TOKEN_FILE.write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def get_service():
    """Return the cached Gmail API service (builds it on first call)."""
    global _service
    if _service is None:
        _service = _build_service()
    return _service


# ──────────────────────────────────────────────────────────────────────────────
# Helper utilities
# ──────────────────────────────────────────────────────────────────────────────


def _decode_payload(part: dict) -> str:
    """Base64-decode the body payload of a Gmail message part."""
    data = part.get("body", {}).get("data", "")
    if not data:
        return ""
    return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")


def _extract_headers(headers: list[dict], *names: str) -> dict[str, str]:
    """Return a dict of {name: value} for the requested header names."""
    result: dict[str, str] = {}
    for h in headers:
        if h["name"].lower() in {n.lower() for n in names}:
            result[h["name"].lower()] = h["value"]
    return result


def _parse_message(msg: dict) -> dict[str, Any]:
    """Convert a raw Gmail API message into a clean dict."""
    payload = msg.get("payload", {})
    headers = payload.get("headers", [])
    meta = _extract_headers(headers, "Subject", "From", "To", "Date")

    # Extract plain-text body
    body = ""
    parts = payload.get("parts", [])
    if parts:
        for part in parts:
            if part.get("mimeType") == "text/plain":
                body = _decode_payload(part)
                break
    else:
        body = _decode_payload(payload)

    return {
        "id": msg["id"],
        "thread_id": msg.get("threadId", ""),
        "subject": meta.get("subject", "(no subject)"),
        "from": meta.get("from", ""),
        "to": meta.get("to", ""),
        "date": meta.get("date", ""),
        "snippet": msg.get("snippet", ""),
        "body": body,
        "labels": msg.get("labelIds", []),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────


def list_inbox(max_results: int = 10, query: str = "") -> list[dict[str, Any]]:
    """Return up to *max_results* messages from the inbox."""
    svc = get_service()
    q = f"in:inbox {query}".strip()
    result = svc.users().messages().list(userId="me", q=q, maxResults=max_results).execute()
    messages = result.get("messages", [])
    detailed = []
    for m in messages:
        full = svc.users().messages().get(userId="me", id=m["id"], format="full").execute()
        detailed.append(_parse_message(full))
    return detailed


def send_email(to: str, subject: str, body: str, reply_to_id: str | None = None) -> dict[str, Any]:
    """Compose and send an email; optionally thread it as a reply."""
    svc = get_service()
    mime = MIMEMultipart("alternative")
    mime["to"] = to
    mime["from"] = settings.email_address
    mime["subject"] = subject
    if reply_to_id:
        mime["In-Reply-To"] = reply_to_id
        mime["References"] = reply_to_id

    mime.attach(MIMEText(body, "plain"))
    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
    body_payload: dict[str, Any] = {"raw": raw}
    if reply_to_id:
        # Find the thread
        try:
            orig = svc.users().messages().get(userId="me", id=reply_to_id, format="minimal").execute()
            body_payload["threadId"] = orig.get("threadId", "")
        except Exception:
            pass

    sent = svc.users().messages().send(userId="me", body=body_payload).execute()
    log.info("Email sent. Message id: %s", sent["id"])
    return sent


def save_draft(to: str, subject: str, body: str) -> dict[str, Any]:
    """Save an email as a Gmail draft."""
    svc = get_service()
    mime = MIMEMultipart("alternative")
    mime["to"] = to
    mime["from"] = settings.email_address
    mime["subject"] = subject
    mime.attach(MIMEText(body, "plain"))
    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
    draft = svc.users().drafts().create(userId="me", body={"message": {"raw": raw}}).execute()
    log.info("Draft saved. Draft id: %s", draft["id"])
    return draft


def search_emails(query: str, max_results: int = 10) -> list[dict[str, Any]]:
    """Search Gmail with *query* and return matching messages."""
    return list_inbox(max_results=max_results, query=query)


def delete_email(message_id: str) -> None:
    """Trash a Gmail message by ID."""
    svc = get_service()
    svc.users().messages().trash(userId="me", id=message_id).execute()
    log.info("Message %s moved to trash.", message_id)


def forward_email(message_id: str, to: str) -> dict[str, Any]:
    """Forward an existing message to *to*."""
    svc = get_service()
    orig = svc.users().messages().get(userId="me", id=message_id, format="full").execute()
    parsed = _parse_message(orig)
    fwd_subject = (
        parsed["subject"]
        if parsed["subject"].startswith("Fwd:")
        else f"Fwd: {parsed['subject']}"
    )
    fwd_body = (
        f"---------- Forwarded message ----------\n"
        f"From: {parsed['from']}\n"
        f"Date: {parsed['date']}\n"
        f"Subject: {parsed['subject']}\n"
        f"To: {parsed['to']}\n\n"
        f"{parsed['body']}"
    )
    return send_email(to=to, subject=fwd_subject, body=fwd_body)
