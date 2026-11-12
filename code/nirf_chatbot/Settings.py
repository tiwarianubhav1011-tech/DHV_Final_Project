"""
Application settings loaded from environment variables.

Every secret or deployment-specific value lives here so that backend
modules never hard-code credentials.
"""

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


@lru_cache(maxsize=1)
def gemini() -> str:
    """Return the Sarvam AI API key from the environment."""
    key = os.getenv("SARVAM_API_KEY", "")
    if not key:
        raise RuntimeError(
            "SARVAM_API_KEY is not set. "
            "Add it to your .env file or export it as an environment variable."
        )
    return key


def database_url() -> str:
    """Return the PostgreSQL connection URL from the environment."""
    url = os.getenv("DATABASE_URL", "")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. "
            "Add it to your .env file, e.g. "
            "DATABASE_URL=postgresql://user:pass@host:5432/dbname"
        )
    # If the scheme is plain postgresql://, use postgresql+psycopg2://
    # to match the installed psycopg2-binary driver
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    elif url.startswith("postgres://"):
        url = "postgresql+psycopg2://" + url[len("postgres://"):]
    return url
