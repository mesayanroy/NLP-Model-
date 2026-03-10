"""
Train the NLP intent classifier.

Algorithm: TF-IDF vectorisation → Logistic Regression.
The trained pipeline is persisted to backend/training/model/ via joblib so
that the FastAPI server and CLI can load it without re-training.

Usage:
    python -m backend.training.train
"""
from __future__ import annotations

import os
import sys
import logging
from pathlib import Path

import joblib
import nltk
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from backend.training.data import TRAINING_SAMPLES, INTENT_LABELS

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).parent / "model"
MODEL_PATH = MODEL_DIR / "intent_classifier.joblib"
LABEL_PATH = MODEL_DIR / "labels.joblib"


def _download_nltk() -> None:
    """Silently ensure required NLTK assets are available."""
    for pkg in ("punkt", "stopwords", "wordnet"):
        try:
            nltk.data.find(f"tokenizers/{pkg}" if pkg == "punkt" else f"corpora/{pkg}")
        except LookupError:
            nltk.download(pkg, quiet=True)


def _preprocess(text: str) -> str:
    """Lowercase, remove punctuation, and stem tokens."""
    from nltk.corpus import stopwords
    from nltk.stem import PorterStemmer
    import re

    stemmer = PorterStemmer()
    stop_words = set(stopwords.words("english"))
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    tokens = text.split()
    tokens = [stemmer.stem(t) for t in tokens if t not in stop_words]
    return " ".join(tokens)


def build_pipeline() -> Pipeline:
    """Return an untrained sklearn Pipeline."""
    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    ngram_range=(1, 2),
                    max_features=10_000,
                    preprocessor=_preprocess,
                    sublinear_tf=True,
                ),
            ),
            (
                "clf",
                LogisticRegression(
                    max_iter=1000,
                    C=5.0,
                    solver="lbfgs",
                    random_state=42,
                ),
            ),
        ]
    )


def train() -> Pipeline:
    """Train the intent classifier and persist it to disk."""
    _download_nltk()

    texts, labels = zip(*TRAINING_SAMPLES)
    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels
    )

    log.info("Training intent classifier on %d samples …", len(X_train))
    pipeline = build_pipeline()
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    report = classification_report(y_test, y_pred, target_names=sorted(set(labels)))
    log.info("Evaluation on held-out test set:\n%s", report)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, MODEL_PATH)
    joblib.dump(INTENT_LABELS, LABEL_PATH)
    log.info("Model saved to %s", MODEL_PATH)

    return pipeline


def load_pipeline() -> Pipeline:
    """Load the persisted pipeline, training if it does not exist yet."""
    if not MODEL_PATH.exists():
        log.info("No pre-trained model found — training now …")
        return train()
    return joblib.load(MODEL_PATH)


if __name__ == "__main__":
    train()
    print("Training complete.")
