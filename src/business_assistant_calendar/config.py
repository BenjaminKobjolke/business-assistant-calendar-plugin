"""Google Calendar settings loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from .constants import (
    DEFAULT_CALENDAR_ID,
    DEFAULT_OAUTH_PORT,
    DEFAULT_TIMEZONE,
    DEFAULT_TOKEN_PATH,
    ENV_GOOGLE_CALENDAR_CREDENTIALS_PATH,
    ENV_GOOGLE_CALENDAR_FREE_CHECK_IDS,
    ENV_GOOGLE_CALENDAR_ID,
    ENV_GOOGLE_CALENDAR_OAUTH_PORT,
    ENV_GOOGLE_CALENDAR_TIMEZONE,
    ENV_GOOGLE_CALENDAR_TOKEN_PATH,
)


@dataclass(frozen=True)
class CalendarSettings:
    """Google Calendar connection settings."""

    credentials_path: str
    token_path: str = DEFAULT_TOKEN_PATH
    calendar_id: str = DEFAULT_CALENDAR_ID
    timezone: str = DEFAULT_TIMEZONE
    oauth_port: int = DEFAULT_OAUTH_PORT
    free_check_calendar_ids: tuple[str, ...] = field(default_factory=tuple)


def load_calendar_settings() -> CalendarSettings | None:
    """Load calendar settings from environment variables.

    Returns None if GOOGLE_CALENDAR_CREDENTIALS_PATH is not configured.
    """
    credentials_path = os.environ.get(ENV_GOOGLE_CALENDAR_CREDENTIALS_PATH, "")
    if not credentials_path:
        return None

    free_check_raw = os.environ.get(ENV_GOOGLE_CALENDAR_FREE_CHECK_IDS, "")
    free_check_ids = tuple(
        cid.strip() for cid in free_check_raw.split(",") if cid.strip()
    )

    return CalendarSettings(
        credentials_path=credentials_path,
        token_path=os.environ.get(ENV_GOOGLE_CALENDAR_TOKEN_PATH, DEFAULT_TOKEN_PATH),
        calendar_id=os.environ.get(ENV_GOOGLE_CALENDAR_ID, DEFAULT_CALENDAR_ID),
        timezone=os.environ.get(ENV_GOOGLE_CALENDAR_TIMEZONE, DEFAULT_TIMEZONE),
        oauth_port=int(
            os.environ.get(ENV_GOOGLE_CALENDAR_OAUTH_PORT, str(DEFAULT_OAUTH_PORT))
        ),
        free_check_calendar_ids=free_check_ids,
    )
