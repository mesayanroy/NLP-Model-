"""
Voice service — microphone input → text, and text → speech output.

Dependencies:
  - SpeechRecognition  (pip install SpeechRecognition)
  - pyttsx3            (pip install pyttsx3)
  - pyaudio            (pip install pyaudio)  ← required by SpeechRecognition for mic access

On headless / CI systems voice features are gracefully disabled.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Lazy-import so the rest of the app works even without audio libs installed.
# ──────────────────────────────────────────────────────────────────────────────
try:
    import speech_recognition as sr

    _SR_AVAILABLE = True
except ImportError:
    _SR_AVAILABLE = False
    log.warning("SpeechRecognition not available — voice input disabled.")

try:
    import pyttsx3

    _TTS_AVAILABLE = True
    _tts_engine = pyttsx3.init()
    # Slightly slower rate for clarity
    _tts_engine.setProperty("rate", 165)
except Exception:
    _TTS_AVAILABLE = False
    log.warning("pyttsx3 not available — voice output disabled.")


# ──────────────────────────────────────────────────────────────────────────────
# Speech-to-text
# ──────────────────────────────────────────────────────────────────────────────


def listen(timeout: int = 8, phrase_limit: int = 20) -> str | None:
    """
    Capture a voice utterance from the default microphone and return the
    transcribed text.  Returns *None* if recognition fails or is unavailable.

    Parameters
    ----------
    timeout:      seconds to wait for speech to start.
    phrase_limit: maximum seconds of speech to capture.
    """
    if not _SR_AVAILABLE:
        log.error("SpeechRecognition library is not installed.")
        return None

    recognizer = sr.Recognizer()
    recognizer.pause_threshold = 1.0  # seconds of silence before ending phrase

    try:
        with sr.Microphone() as source:
            log.info("Adjusting for ambient noise …")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            log.info("Listening …")
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)

        text = recognizer.recognize_google(audio)
        log.info("Heard: %s", text)
        return text

    except sr.WaitTimeoutError:
        log.warning("No speech detected within timeout.")
    except sr.UnknownValueError:
        log.warning("Could not understand the audio.")
    except sr.RequestError as exc:
        log.error("Speech recognition service error: %s", exc)
    except OSError as exc:
        log.error("Microphone error: %s", exc)

    return None


# ──────────────────────────────────────────────────────────────────────────────
# Text-to-speech
# ──────────────────────────────────────────────────────────────────────────────


def speak(text: str) -> None:
    """
    Speak *text* aloud using the system TTS engine.
    Falls back to printing if TTS is unavailable.
    """
    if _TTS_AVAILABLE:
        try:
            _tts_engine.say(text)
            _tts_engine.runAndWait()
            return
        except Exception as exc:
            log.warning("TTS playback failed: %s", exc)
    print(f"[TTS] {text}")
