"""Package setup for NLP Email Assistant."""
from setuptools import setup, find_packages

with open("README.md", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="nlp-email-assistant",
    version="1.0.0",
    author="NLP Email Assistant",
    description="AI-powered email assistant with voice support, CLI, and MCP server",
    long_description=long_description,
    long_description_content_type="text/markdown",
    python_requires=">=3.10",
    packages=find_packages(exclude=["tests*"]),
    include_package_data=True,
    install_requires=[
        "fastapi>=0.111.0",
        "uvicorn[standard]>=0.30.1",
        "google-auth>=2.30.0",
        "google-auth-oauthlib>=1.2.0",
        "google-auth-httplib2>=0.2.0",
        "google-api-python-client>=2.133.0",
        "scikit-learn>=1.5.0",
        "numpy>=1.26.4",
        "joblib>=1.4.2",
        "nltk>=3.8.1",
        "openai>=1.35.3",
        "SpeechRecognition>=3.10.4",
        "pyttsx3>=2.90",
        "click>=8.1.7",
        "rich>=13.7.1",
        "prompt_toolkit>=3.0.47",
        "mcp>=1.3.0",
        "python-dotenv>=1.0.1",
        "httpx>=0.27.0",
        "pydantic>=2.7.4",
        "pydantic-settings>=2.3.4",
    ],
    extras_require={
        "audio": ["pyaudio>=0.2.14"],
        "dev": [
            "pytest>=8.2.2",
            "pytest-asyncio>=0.23.7",
        ],
    },
    entry_points={
        "console_scripts": [
            "email-assistant=cli.main:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
)
