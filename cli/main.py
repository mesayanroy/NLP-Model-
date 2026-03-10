"""
NLP Email Assistant — Command-Line Interface

Commands
--------
email-assistant chat    – interactive text chat
email-assistant voice   – interactive voice chat
email-assistant inbox   – show inbox
email-assistant search  – search emails
email-assistant compose – compose and send/draft an email
email-assistant serve   – start the FastAPI server
email-assistant mcp     – start the MCP server
email-assistant train   – (re-)train the NLP model
"""
from __future__ import annotations

import sys
import logging

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import print as rprint

console = Console()
logging.basicConfig(level=logging.WARNING)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _nlp_chat(message: str) -> dict:
    from backend.nlp_model import chat

    return chat(message)


def _print_email_table(emails: list[dict]) -> None:
    if not emails:
        console.print("[yellow]No emails found.[/yellow]")
        return
    table = Table(title="Inbox", show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("From", style="cyan", no_wrap=True)
    table.add_column("Subject", style="bold")
    table.add_column("Date", style="green")
    for i, mail in enumerate(emails, 1):
        table.add_row(
            str(i),
            mail.get("from", "")[:40],
            mail.get("subject", "")[:60],
            mail.get("date", "")[:20],
        )
    console.print(table)


def _confirm(prompt: str) -> bool:
    return click.confirm(prompt, default=False)


# ──────────────────────────────────────────────────────────────────────────────
# CLI group
# ──────────────────────────────────────────────────────────────────────────────


@click.group()
def cli():
    """🤖 NLP Email Assistant — your AI email helper."""


# ──────────────────────────────────────────────────────────────────────────────
# chat
# ──────────────────────────────────────────────────────────────────────────────


@cli.command()
@click.option("--no-color", is_flag=True, default=False, help="Disable rich formatting.")
def chat(no_color: bool):
    """Start an interactive text chat with the assistant."""
    console.print(
        Panel(
            "[bold green]NLP Email Assistant[/bold green]\n"
            "Type your request (e.g. 'write an email to John about the meeting').\n"
            "Commands: [cyan]reset[/cyan] | [cyan]quit[/cyan] / [cyan]exit[/cyan]",
            title="Welcome",
        )
    )

    while True:
        try:
            user_input = click.prompt("\n[You]", prompt_suffix=" ")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]Goodbye![/yellow]")
            break

        cmd = user_input.strip().lower()
        if cmd in ("quit", "exit", "q"):
            console.print("[yellow]Goodbye![/yellow]")
            break
        if cmd == "reset":
            from backend.nlp_model import reset_conversation

            reset_conversation()
            console.print("[green]Conversation reset.[/green]")
            continue
        if not user_input.strip():
            continue

        result = _nlp_chat(user_input)
        intent = result["intent"]
        resp = result["response"]
        conf = result["confidence"]

        if no_color:
            print(f"\n[Assistant] ({intent}, {conf:.0%})\n{resp}")
        else:
            console.print(
                Panel(
                    f"[italic]{resp}[/italic]",
                    title=f"[bold blue]Assistant[/bold blue] · intent=[cyan]{intent}[/cyan] "
                    f"({conf:.0%} confident)",
                    border_style="blue",
                )
            )

        # Interactive send flow
        if intent in ("compose", "reply", "draft") and _confirm("\nWould you like to send/save this?"):
            _interactive_send(result)


def _interactive_send(result: dict) -> None:
    """Prompt for missing fields then send or save the generated email."""
    entities = result.get("entities", {})
    to = entities.get("recipient_email") or click.prompt("Recipient email")
    subject = entities.get("subject_hint") or click.prompt("Subject")
    body = result["response"]
    console.print(
        Panel(body, title="[bold]Email preview[/bold]", border_style="green")
    )
    action = click.prompt("Action", type=click.Choice(["send", "draft", "cancel"]), default="send")
    if action == "send":
        try:
            from backend.email_service import send_email

            send_email(to=to, subject=subject, body=body)
            console.print("[green]✅ Email sent![/green]")
        except Exception as exc:
            console.print(f"[red]Error sending email: {exc}[/red]")
    elif action == "draft":
        try:
            from backend.email_service import save_draft

            save_draft(to=to, subject=subject, body=body)
            console.print("[green]💾 Draft saved![/green]")
        except Exception as exc:
            console.print(f"[red]Error saving draft: {exc}[/red]")


# ──────────────────────────────────────────────────────────────────────────────
# voice
# ──────────────────────────────────────────────────────────────────────────────


@cli.command()
def voice():
    """Start an interactive voice chat (requires microphone)."""
    from backend.voice_service import listen, speak

    console.print(
        Panel(
            "[bold green]Voice Mode[/bold green]\n"
            "Speak your email request. Say [cyan]'quit'[/cyan] to exit.",
            title="🎤 Voice Chat",
        )
    )

    while True:
        console.print("\n[dim]Listening … (press Ctrl-C to stop)[/dim]")
        try:
            text = listen()
        except KeyboardInterrupt:
            console.print("\n[yellow]Voice mode stopped.[/yellow]")
            break

        if text is None:
            console.print("[yellow]Could not understand — please try again.[/yellow]")
            speak("Sorry, I could not understand. Please try again.")
            continue

        console.print(f"[cyan]Heard:[/cyan] {text}")

        if text.lower().strip() in ("quit", "exit", "stop"):
            speak("Goodbye!")
            break

        result = _nlp_chat(text)
        resp = result["response"]
        intent = result["intent"]

        console.print(
            Panel(
                f"[italic]{resp}[/italic]",
                title=f"[bold blue]Assistant[/bold blue] · intent=[cyan]{intent}[/cyan]",
                border_style="blue",
            )
        )
        speak(resp)


# ──────────────────────────────────────────────────────────────────────────────
# inbox
# ──────────────────────────────────────────────────────────────────────────────


@cli.command()
@click.option("-n", "--max-results", default=10, show_default=True, help="Number of emails to show.")
@click.option("-q", "--query", default="", help="Gmail search filter (e.g. 'is:unread').")
def inbox(max_results: int, query: str):
    """Read your Gmail inbox."""
    try:
        from backend.email_service import list_inbox

        console.print(f"[dim]Fetching up to {max_results} email(s) …[/dim]")
        emails = list_inbox(max_results=max_results, query=query)
        _print_email_table(emails)
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        sys.exit(1)


# ──────────────────────────────────────────────────────────────────────────────
# search
# ──────────────────────────────────────────────────────────────────────────────


@cli.command()
@click.argument("query")
@click.option("-n", "--max-results", default=10, show_default=True)
def search(query: str, max_results: int):
    """Search emails by a Gmail query string."""
    try:
        from backend.email_service import search_emails

        emails = search_emails(query=query, max_results=max_results)
        _print_email_table(emails)
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        sys.exit(1)


# ──────────────────────────────────────────────────────────────────────────────
# compose
# ──────────────────────────────────────────────────────────────────────────────


@cli.command()
@click.option("--to", prompt="Recipient email", help="Recipient email address.")
@click.option("--subject", prompt="Subject", help="Email subject.")
@click.option("--body", default="", help="Email body (leave empty to describe and AI-generate).")
@click.option("--draft", "save_as_draft", is_flag=True, default=False, help="Save as draft instead of sending.")
def compose(to: str, subject: str, body: str, save_as_draft: bool):
    """Compose and send (or draft) an email with optional AI assistance."""
    if not body:
        desc = click.prompt("Describe what you want to say")
        result = _nlp_chat(f"write an email to {to} about {subject}: {desc}")
        body = result["response"]
        console.print(Panel(body, title="[bold]AI-generated email[/bold]", border_style="green"))
        if not _confirm("Use this content?"):
            body = click.prompt("Enter email body manually")

    if save_as_draft:
        try:
            from backend.email_service import save_draft

            save_draft(to=to, subject=subject, body=body)
            console.print("[green]💾 Draft saved![/green]")
        except Exception as exc:
            console.print(f"[red]Error saving draft: {exc}[/red]")
            sys.exit(1)
    else:
        try:
            from backend.email_service import send_email

            send_email(to=to, subject=subject, body=body)
            console.print("[green]✅ Email sent![/green]")
        except Exception as exc:
            console.print(f"[red]Error sending email: {exc}[/red]")
            sys.exit(1)


# ──────────────────────────────────────────────────────────────────────────────
# serve
# ──────────────────────────────────────────────────────────────────────────────


@cli.command()
@click.option("--host", default="0.0.0.0", show_default=True)
@click.option("--port", default=8000, show_default=True)
@click.option("--reload", is_flag=True, default=False, help="Enable hot-reload (dev mode).")
def serve(host: str, port: int, reload: bool):
    """Start the FastAPI HTTP server."""
    try:
        import uvicorn

        console.print(
            Panel(
                f"Starting server at [link=http://{host}:{port}]http://{host}:{port}[/link]\n"
                f"API docs at [link=http://{host}:{port}/docs]http://{host}:{port}/docs[/link]\n"
                f"Frontend  at [link=http://{host}:{port}/frontend]http://{host}:{port}/frontend[/link]",
                title="[bold green]NLP Email Assistant Server[/bold green]",
            )
        )
        uvicorn.run(
            "backend.app:app",
            host=host,
            port=port,
            reload=reload,
        )
    except ImportError:
        console.print("[red]uvicorn not installed. Run: pip install uvicorn[/red]")
        sys.exit(1)


# ──────────────────────────────────────────────────────────────────────────────
# mcp
# ──────────────────────────────────────────────────────────────────────────────


@cli.command()
def mcp():
    """Start the MCP (Model Context Protocol) server."""
    from backend.mcp_server import run

    console.print(
        Panel(
            "Starting MCP server …\n"
            "Connect your MCP client (e.g. Claude Desktop) to this process.",
            title="[bold green]MCP Server[/bold green]",
        )
    )
    run()


# ──────────────────────────────────────────────────────────────────────────────
# train
# ──────────────────────────────────────────────────────────────────────────────


@cli.command()
def train():
    """Train (or re-train) the intent classification model."""
    console.print("[dim]Training NLP model …[/dim]")
    try:
        from backend.training.train import train as _train

        _train()
        console.print("[green]✅ Model trained and saved.[/green]")
    except Exception as exc:
        console.print(f"[red]Training failed: {exc}[/red]")
        sys.exit(1)


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────


def main():
    cli()


if __name__ == "__main__":
    main()
