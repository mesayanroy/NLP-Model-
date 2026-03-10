"""
MCP (Model Context Protocol) Server for the NLP Email Assistant.

Exposes the following tools that MCP clients (e.g. Claude Desktop) can call:
  - chat              – Converse with the NLP email assistant
  - read_inbox        – List inbox emails
  - search_emails     – Search emails by query
  - send_email        – Send an email
  - save_draft        – Save an email as a draft
  - reply_email       – Reply to an email
  - forward_email     – Forward an email
  - delete_email      – Trash an email
  - reset_chat        – Reset conversation history

Run with:
    python -m backend.mcp_server
or:
    email-assistant mcp
"""
from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# MCP server bootstrap
# ──────────────────────────────────────────────────────────────────────────────
try:
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP(
        "NLP Email Assistant",
        instructions=(
            "You are an intelligent email assistant. "
            "You can compose, read, reply, forward, search and manage emails. "
            "Always act professionally and help the user efficiently."
        ),
    )
    _MCP_AVAILABLE = True
except ImportError:
    _MCP_AVAILABLE = False
    log.warning("mcp package not installed — MCP server disabled.")


# ──────────────────────────────────────────────────────────────────────────────
# Tools
# ──────────────────────────────────────────────────────────────────────────────


if _MCP_AVAILABLE:

    @mcp.tool()
    def chat(message: str) -> dict[str, Any]:
        """
        Chat with the NLP email assistant.

        Parameters
        ----------
        message : str
            The user's message or voice transcript.

        Returns
        -------
        dict with keys: intent, confidence, entities, response
        """
        from backend.nlp_model import chat as _chat

        return _chat(message)

    @mcp.tool()
    def reset_chat() -> dict[str, str]:
        """Reset the conversation history with the assistant."""
        from backend.nlp_model import reset_conversation

        reset_conversation()
        return {"status": "conversation reset"}

    @mcp.tool()
    def read_inbox(max_results: int = 10, query: str = "") -> list[dict[str, Any]]:
        """
        List emails from the inbox.

        Parameters
        ----------
        max_results : int
            Maximum number of emails to return (1-50).
        query : str
            Optional Gmail search filter (e.g. "is:unread from:alice").
        """
        from backend.email_service import list_inbox

        return list_inbox(max_results=min(max_results, 50), query=query)

    @mcp.tool()
    def search_emails(query: str, max_results: int = 10) -> list[dict[str, Any]]:
        """
        Search emails by a Gmail search query.

        Parameters
        ----------
        query : str
            Gmail-compatible search string (e.g. "subject:meeting from:bob").
        max_results : int
            Maximum number of results to return.
        """
        from backend.email_service import search_emails as _search

        return _search(query=query, max_results=min(max_results, 50))

    @mcp.tool()
    def send_email(to: str, subject: str, body: str, reply_to_id: str = "") -> dict[str, Any]:
        """
        Compose and send an email.

        Parameters
        ----------
        to : str
            Recipient email address.
        subject : str
            Email subject line.
        body : str
            Plain-text email body.
        reply_to_id : str
            Optional message-id to thread as a reply.
        """
        from backend.email_service import send_email as _send

        return _send(
            to=to,
            subject=subject,
            body=body,
            reply_to_id=reply_to_id if reply_to_id else None,
        )

    @mcp.tool()
    def save_draft(to: str, subject: str, body: str) -> dict[str, Any]:
        """
        Save an email as a Gmail draft.

        Parameters
        ----------
        to : str
            Recipient email address.
        subject : str
            Email subject line.
        body : str
            Plain-text email body.
        """
        from backend.email_service import save_draft as _draft

        return _draft(to=to, subject=subject, body=body)

    @mcp.tool()
    def reply_email(message_id: str, body: str) -> dict[str, Any]:
        """
        Reply to an existing email.

        Parameters
        ----------
        message_id : str
            Gmail message ID of the email to reply to.
        body : str
            Plain-text reply body.
        """
        from backend.email_service import get_service, _parse_message, send_email as _send

        svc = get_service()
        orig = svc.users().messages().get(userId="me", id=message_id, format="full").execute()
        parsed = _parse_message(orig)
        subject = (
            parsed["subject"]
            if parsed["subject"].startswith("Re:")
            else f"Re: {parsed['subject']}"
        )
        return _send(to=parsed["from"], subject=subject, body=body, reply_to_id=message_id)

    @mcp.tool()
    def forward_email(message_id: str, to: str) -> dict[str, Any]:
        """
        Forward an existing email to another recipient.

        Parameters
        ----------
        message_id : str
            Gmail message ID of the email to forward.
        to : str
            Recipient email address.
        """
        from backend.email_service import forward_email as _fwd

        return _fwd(message_id=message_id, to=to)

    @mcp.tool()
    def delete_email(message_id: str) -> dict[str, str]:
        """
        Move an email to the Gmail trash.

        Parameters
        ----------
        message_id : str
            Gmail message ID of the email to delete.
        """
        from backend.email_service import delete_email as _del

        _del(message_id)
        return {"status": "deleted", "message_id": message_id}


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────


def run() -> None:
    if not _MCP_AVAILABLE:
        print("ERROR: mcp package not installed. Run: pip install mcp")
        return
    mcp.run()


if __name__ == "__main__":
    run()
