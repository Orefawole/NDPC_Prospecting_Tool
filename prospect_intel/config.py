"""Settings loaded from the environment (.env supported)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # optional
    pass

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    google_places_api_key: str = field(default_factory=lambda: os.getenv("GOOGLE_PLACES_API_KEY", ""))
    claude_model: str = field(default_factory=lambda: os.getenv("CLAUDE_MODEL", "claude-opus-5-5"))
    claude_effort: str = field(default_factory=lambda: os.getenv("CLAUDE_EFFORT", "medium"))
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'data' / 'prospects.db'}")
    )
    user_agent: str = field(
        default_factory=lambda: os.getenv("CRAWL_USER_AGENT", "ProspectIntelBot/0.1")
    )
    crawl_delay: float = field(default_factory=lambda: float(os.getenv("CRAWL_DELAY_SECONDS", "2")))
    max_pages_per_site: int = field(default_factory=lambda: int(os.getenv("CRAWL_MAX_PAGES_PER_SITE", "6")))

    # MVP scope: sectors confirmed by the user; cities are a default to revisit.
    sectors: tuple[str, ...] = ("finance", "health", "insurance")
    cities: tuple[str, ...] = ("Lagos", "Abuja")


settings = Settings()
