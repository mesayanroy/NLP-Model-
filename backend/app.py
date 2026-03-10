"""
FastAPI backend for the NLP Email Assistant.

Endpoints
---------
GET  /              – health check
POST /chat          – chat with the NLP model
POST /email/send    – send an email
GET  /email/inbox   – list inbox messages
GET  /email/search  – search emails
DELETE /email/{id}  – trash an email
POST /email/draft   – save a draft
POST /email/forward – forward a message
POST /email/reply   – reply to a message
POST /voice/listen  – capture one voice utterance (blocking)
POST /train         – re-train the intent classifier
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr, field_validator
import os
from pathlib import Path

from backend.config import settings
from backend.nlp_model import chat as nlp_chat, reset_conversation

log = logging.getLogger(__name__)

app = FastAPI(
    title="NLP Email Assistant",
    description="AI-powered email assistant with voice support",
    version="1.0.0",
)

# Allow all origins in dev; tighten in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the frontend static files
_FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if _FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_FRONTEND_DIR)), name="static")


# ──────────────────────────────────────────────────────────────────────────────
# Pydantic models
# ──────────────────────────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    message: str

    @field_validator("message")
    @classmethod
    def message_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message must not be empty")
        return v.strip()


class ChatResponse(BaseModel):
    intent: str
    confidence: float
    entities: dict[str, str]
    response: str


class SendEmailRequest(BaseModel):
    to: str
    subject: str
    body: str
    reply_to_id: Optional[str] = None


class DraftRequest(BaseModel):
    to: str
    subject: str
    body: str


class ForwardRequest(BaseModel):
    message_id: str
    to: str


class ReplyRequest(BaseModel):
    message_id: str
    body: str


# ──────────────────────────────────────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────────────────────────────────────


@app.get("/", tags=["health"])
def root():
    return {"status": "ok", "service": "NLP Email Assistant"}


@app.get("/frontend", tags=["frontend"], include_in_schema=False)
def serve_frontend():
    index = _FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    raise HTTPException(status_code=404, detail="Frontend not found")


@app.post("/chat", response_model=ChatResponse, tags=["nlp"])
def chat_endpoint(req: ChatRequest):
    """Send a message to the NLP assistant and receive a reply."""
    try:
        result = nlp_chat(req.message)
        return ChatResponse(**result)
    except Exception as exc:
        log.exception("Chat error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/chat/reset", tags=["nlp"])
def reset_chat():
    """Clear the conversation history."""
    reset_conversation()
    return {"status": "conversation reset"}


@app.post("/train", tags=["nlp"])
def retrain():
    """Re-train the intent classifier with the built-in training data."""
    try:
        from backend.training.train import train

        train()
        # Reload the global pipeline
        from backend import nlp_model

        nlp_model._pipeline = None  # force reload
        return {"status": "training complete"}
    except Exception as exc:
        log.exception("Training error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/email/inbox", tags=["email"])
def get_inbox(
    max_results: int = Query(default=10, ge=1, le=50),
    query: str = Query(default=""),
):
    """List inbox emails."""
    try:
        from backend.email_service import list_inbox

        return list_inbox(max_results=max_results, query=query)
    except Exception as exc:
        log.exception("Inbox error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/email/search", tags=["email"])
def search_email(
    q: str = Query(..., description="Gmail search query"),
    max_results: int = Query(default=10, ge=1, le=50),
):
    """Search emails by query."""
    try:
        from backend.email_service import search_emails

        return search_emails(query=q, max_results=max_results)
    except Exception as exc:
        log.exception("Search error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/email/send", tags=["email"])
def send_email_endpoint(req: SendEmailRequest):
    """Send an email."""
    try:
        from backend.email_service import send_email

        result = send_email(
            to=req.to,
            subject=req.subject,
            body=req.body,
            reply_to_id=req.reply_to_id,
        )
        return {"status": "sent", "message_id": result.get("id")}
    except Exception as exc:
        log.exception("Send email error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/email/draft", tags=["email"])
def save_draft_endpoint(req: DraftRequest):
    """Save an email as a draft."""
    try:
        from backend.email_service import save_draft

        result = save_draft(to=req.to, subject=req.subject, body=req.body)
        return {"status": "draft saved", "draft_id": result.get("id")}
    except Exception as exc:
        log.exception("Draft error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/email/forward", tags=["email"])
def forward_email_endpoint(req: ForwardRequest):
    """Forward an email."""
    try:
        from backend.email_service import forward_email

        result = forward_email(message_id=req.message_id, to=req.to)
        return {"status": "forwarded", "message_id": result.get("id")}
    except Exception as exc:
        log.exception("Forward error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/email/reply", tags=["email"])
def reply_email_endpoint(req: ReplyRequest):
    """Reply to an email."""
    try:
        from backend.email_service import get_service, _parse_message

        svc = get_service()
        orig = svc.users().messages().get(userId="me", id=req.message_id, format="full").execute()
        parsed = _parse_message(orig)
        from backend.email_service import send_email

        subject = (
            parsed["subject"]
            if parsed["subject"].startswith("Re:")
            else f"Re: {parsed['subject']}"
        )
        result = send_email(
            to=parsed["from"],
            subject=subject,
            body=req.body,
            reply_to_id=req.message_id,
        )
        return {"status": "replied", "message_id": result.get("id")}
    except Exception as exc:
        log.exception("Reply error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.delete("/email/{message_id}", tags=["email"])
def delete_email_endpoint(message_id: str):
    """Move an email to trash."""
    try:
        from backend.email_service import delete_email

        delete_email(message_id)
        return {"status": "deleted", "message_id": message_id}
    except Exception as exc:
        log.exception("Delete error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/voice/listen", tags=["voice"])
def voice_listen():
    """Capture one voice utterance and return the transcribed text."""
    try:
        from backend.voice_service import listen

        text = listen()
        if text is None:
            raise HTTPException(status_code=400, detail="Could not capture voice input")
        return {"text": text}
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Voice listen error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
