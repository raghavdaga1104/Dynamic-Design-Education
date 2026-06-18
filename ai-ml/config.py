"""
config.py
---------
Single source of truth for all environment-based configuration.

FIX (Review §6.3 / §8.3):
  Previously GROQ_API_KEY, GROQ_MODEL, and GROQ_BASE_URL were
  duplicated independently in rag_engine.py and ats_engine.py.
  Any developer who changed one file and forgot the other would get
  silent, hard-to-debug failures. Both engines now import from here.

Usage
-----
  from config import settings

  key   = settings.groq_api_key
  model = settings.groq_model

Environment variables (set in .env or shell):
  GROQ_API_KEY      — your Groq API key (get free at console.groq.com)
  GROQ_MODEL        — LLM model name (default: llama-3.1-8b-instant)
  ALLOWED_ORIGINS   — comma-separated CORS origins (default: localhost:3000)
  MCTS_ITERATIONS   — MCTS iterations per recommendation (default: 150)
  STATE_DIR         — path to learner state JSON files
  LOG_LEVEL         — logging level: DEBUG | INFO | WARNING (default: INFO)
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

# ─────────────────────────────────────────────────────────────────
#  GROQ / LLM
# ─────────────────────────────────────────────────────────────────

GROQ_API_KEY  = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL    = os.environ.get("GROQ_MODEL",   "llama-3.1-8b-instant")
GROQ_BASE_URL = "https://api.groq.com/openai/v1/chat/completions"

if not GROQ_API_KEY:
    logging.warning(
        "GROQ_API_KEY is not set. "
        "RAG chatbot and ATS improvement will use fallback responses. "
        "Get a free key (no credit card) at https://console.groq.com"
    )

# ─────────────────────────────────────────────────────────────────
#  CORS
# ─────────────────────────────────────────────────────────────────

_raw_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173")
ALLOWED_ORIGINS: list = [o.strip() for o in _raw_origins.split(",") if o.strip()]

# ─────────────────────────────────────────────────────────────────
#  MCTS
# ─────────────────────────────────────────────────────────────────

MCTS_ITERATIONS: int = int(os.environ.get("MCTS_ITERATIONS", "150"))

# ─────────────────────────────────────────────────────────────────
#  STORAGE
# ─────────────────────────────────────────────────────────────────

_default_state_dir = Path(__file__).parent / "data" / "learner_states"
STATE_DIR: Path = Path(os.environ.get("STATE_DIR", str(_default_state_dir)))

# ─────────────────────────────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────────────────────────────

LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO").upper()

def configure_logging() -> None:
    """
    Configure root logger with a consistent format.
    Call once from main.py at startup.
    Replaces all ad-hoc print() / print('[DEBUG]...') calls.
    """
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )