# NLP Email Assistant

An AI-powered email assistant for **laptops and tablets** that helps you
compose, read, reply to, search, and manage your Gmail using natural language
— by text **or voice**.

```
┌──────────────────────────────────────────────────────────────┐
│  You: "Write an email to Alice about the project deadline"   │
│  Assistant: [composes a professional email draft instantly]  │
└──────────────────────────────────────────────────────────────┘
```

## Features

| Feature | Details |
|---|---|
| 🧠 **NLP Intent Classifier** | Custom-trained TF-IDF + Logistic Regression model (scikit-learn) |
| 🤖 **AI Email Generation** | OpenAI GPT-3.5-turbo with graceful template fallback |
| 📧 **Gmail Integration** | Read, compose, reply, forward, draft, search, delete via Gmail API |
| 🎤 **Voice Input** | Microphone → speech-to-text using SpeechRecognition (offline) |
| 🔊 **Voice Output** | Text-to-speech using pyttsx3 |
| 💻 **CLI** | `email-assistant chat / voice / inbox / compose / serve / mcp / train` |
| 🌐 **REST API** | FastAPI backend with Swagger UI at `/docs` |
| 🖥️ **Web Frontend** | Clean, responsive HTML/CSS/JS dashboard with voice button |
| 🔌 **MCP Server** | Model Context Protocol server for Claude Desktop & other MCP clients |

---

## Quick Start

### 1 — Install dependencies

```bash
pip install -r requirements.txt
```

> **Audio support** (voice input/output) requires PortAudio.
> - **Ubuntu / Debian:** `sudo apt-get install portaudio19-dev`
> - **macOS:** `brew install portaudio`
> - **Windows:** `pip install pyaudio` (pre-built wheels available)

### 2 — Configure environment

```bash
cp .env.example .env
# Edit .env and set your OPENAI_API_KEY
# (Gmail setup described below)
```

### 3 — Train the NLP model

```bash
python -m backend.training.train
```

The trained model is saved to `backend/training/model/`.

### 4a — Launch the web server + frontend

```bash
email-assistant serve
# or:
python -m uvicorn backend.app:app --reload
```

Open <http://localhost:8000/frontend> in your browser.  
API docs: <http://localhost:8000/docs>

### 4b — Use the CLI

```bash
# Interactive text chat
email-assistant chat

# Voice mode (requires microphone)
email-assistant voice

# Read your inbox
email-assistant inbox

# Compose an email
email-assistant compose --to alice@example.com --subject "Meeting request"

# Search emails
email-assistant search "from:alice is:unread"
```

### 4c — Start the MCP server

```bash
email-assistant mcp
```

Connect Claude Desktop or another MCP client to this process.

---

## Gmail Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project → enable the **Gmail API**.
3. Create an **OAuth 2.0 Desktop** credential.
4. Download `credentials.json` and place it in the project root.
5. Set `GOOGLE_CREDENTIALS_FILE=credentials.json` in `.env`.
6. On first run the browser will open for the OAuth2 consent flow.
   A `token.json` will be saved for subsequent runs.

---

## OpenAI Setup

1. Sign up at <https://platform.openai.com>.
2. Generate an API key.
3. Add it to `.env`: `OPENAI_API_KEY=sk-...`

> The assistant works **without** an OpenAI key using professional
> template-based responses.

---

## Project Structure

```
NLP-Model-/
├── backend/
│   ├── app.py              # FastAPI REST server
│   ├── config.py           # Pydantic settings
│   ├── email_service.py    # Gmail API integration
│   ├── mcp_server.py       # MCP server (FastMCP)
│   ├── nlp_model.py        # Intent classification + AI generation
│   ├── voice_service.py    # Speech recognition + TTS
│   └── training/
│       ├── data.py         # Training samples
│       ├── train.py        # Training script (TF-IDF + LogReg)
│       └── model/          # Persisted model files (generated)
├── cli/
│   └── main.py             # Click CLI entry-point
├── frontend/
│   ├── index.html          # Single-page app
│   ├── style.css           # Responsive styles
│   └── app.js              # Vanilla JS
├── tests/
│   ├── test_nlp.py         # NLP unit tests
│   └── test_api.py         # FastAPI integration tests
├── .env.example            # Environment template
├── requirements.txt
└── setup.py                # pip-installable package
```

---

## Running Tests

```bash
pytest tests/ -v
```

---

## CLI Reference

```
email-assistant --help

Commands:
  chat     Interactive text chat with the assistant
  voice    Interactive voice chat (requires microphone)
  inbox    Show Gmail inbox
  search   Search emails by Gmail query
  compose  Compose and send / draft an email
  serve    Start the FastAPI HTTP server
  mcp      Start the MCP server
  train    (Re-)train the intent classifier
```

---

## Architecture

```
User
 │
 ├──(voice)──► SpeechRecognition ──► text
 │
 ├──(text)───► CLI (Click + Rich)
 │                    │
 │             FastAPI Backend ◄──── Frontend (HTML/JS)
 │                    │
 │             NLP Model (sklearn)
 │                    │
 │             OpenAI GPT-3.5-turbo (optional)
 │                    │
 │             Gmail API (Google OAuth2)
 │
 └──(MCP)────► MCP Server (FastMCP)
```

---

## License

MIT