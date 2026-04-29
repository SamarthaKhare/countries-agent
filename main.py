"""
Entry point for the Countries Agent service.

Usage
-----
    python main.py                      # default: 0.0.0.0:8000
    PORT=3000 python main.py            # custom port
    uvicorn main:app --reload           # development hot-reload

Environment Variables
---------------------
    GROQ_API_KEY   Required. Your Anthropic API key.
    HOST                Optional. Bind host (default: 0.0.0.0)
    PORT                Optional. Bind port (default: 8000)
    LOG_LEVEL           Optional. Uvicorn log level (default: info)
"""

from __future__ import annotations

import logging
import os
import sys

import uvicorn
from dotenv import load_dotenv

load_dotenv()  # loads GROQ_API_KEY (and others) from .env before anything else runs

from api.server import app  

logger = logging.getLogger(__name__)


def _check_env() -> None:
    """Fail fast if required environment variables are missing."""
    if not os.getenv("GROQ_API_KEY"):
        logger.error(
            "GROQ_API_KEY is not set. "
            "Export it before starting the server:\n"
            "  export GROQ_API_KEY=sk-ant-..."
        )
        sys.exit(1)


if __name__ == "__main__":
    _check_env()

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    log_level = os.getenv("LOG_LEVEL", "info")

    logger.info("Starting Countries Agent | host=%s port=%d", host, port)

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        log_level=log_level,
        reload=False,
    )
