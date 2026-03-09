"""Plugin registration — defines PydanticAI tools for calendar operations."""

from __future__ import annotations

import logging

from business_assistant.agent.deps import Deps
from business_assistant.plugins.registry import PluginInfo, PluginRegistry
from pydantic_ai import RunContext, Tool

from .calendar_service import CalendarService
from .config import load_calendar_settings
from .constants import (
    PLUGIN_DATA_CALENDAR_SERVICE,
    PLUGIN_DESCRIPTION,
    PLUGIN_NAME,
    SYSTEM_PROMPT_CALENDAR,
)

logger = logging.getLogger(__name__)


def _get_service(ctx: RunContext[Deps]) -> CalendarService:
    """Retrieve the CalendarService from plugin_data."""
    return ctx.deps.plugin_data[PLUGIN_DATA_CALENDAR_SERVICE]


def _list_calendars(ctx: RunContext[Deps]) -> str:
    """List all available Google calendars (name, ID)."""
    return _get_service(ctx).list_calendars()


def _list_events(
    ctx: RunContext[Deps], date_str: str | None = None, days: int = 1
) -> str:
    """List events for today or a date range. Optionally specify date_str (YYYY-MM-DD) and days."""
    return _get_service(ctx).list_events(date_str=date_str, days=days)


def _create_event(
    ctx: RunContext[Deps],
    summary: str,
    start: str,
    end: str,
    calendar_id: str | None = None,
) -> str:
    """Create a timed event. Provide summary, start and end as ISO datetime strings."""
    return _get_service(ctx).create_event(summary, start, end, calendar_id)


def _create_all_day_event(
    ctx: RunContext[Deps],
    summary: str,
    date_str: str,
    calendar_id: str | None = None,
) -> str:
    """Create an all-day event. Provide summary and date_str (YYYY-MM-DD)."""
    return _get_service(ctx).create_all_day_event(summary, date_str, calendar_id)


def _delete_event(
    ctx: RunContext[Deps], event_id: str, calendar_id: str | None = None
) -> str:
    """Delete an event by Google Calendar event ID."""
    return _get_service(ctx).delete_event(event_id, calendar_id)


def _import_ics_event(
    ctx: RunContext[Deps], ics_data: str, calendar_id: str | None = None
) -> str:
    """Import ICS calendar data to Google Calendar. Chainable with IMAP detect_invite."""
    return _get_service(ctx).import_ics_event(ics_data, calendar_id)


def _find_conflicts(ctx: RunContext[Deps], start: str, end: str) -> str:
    """Check for conflicting events across configured calendars in a time range."""
    return _get_service(ctx).find_conflicts(start, end)


def _search_events(
    ctx: RunContext[Deps], query: str, days_ahead: int = 30
) -> str:
    """Search upcoming events by keyword within the next N days (default 30)."""
    return _get_service(ctx).search_events(query, days_ahead)


def register(registry: PluginRegistry) -> None:
    """Register the calendar plugin with the plugin registry.

    Reads Google Calendar settings from environment. Skips registration
    if GOOGLE_CALENDAR_CREDENTIALS_PATH is not configured.
    """
    settings = load_calendar_settings()
    if settings is None:
        logger.info(
            "Calendar plugin: GOOGLE_CALENDAR_CREDENTIALS_PATH not configured, "
            "skipping registration"
        )
        return

    service = CalendarService(settings)

    tools = [
        Tool(_list_calendars, name="list_calendars"),
        Tool(_list_events, name="list_events"),
        Tool(_create_event, name="create_event"),
        Tool(_create_all_day_event, name="create_all_day_event"),
        Tool(_delete_event, name="delete_event"),
        Tool(_import_ics_event, name="import_ics_event"),
        Tool(_find_conflicts, name="find_conflicts"),
        Tool(_search_events, name="search_events"),
    ]

    info = PluginInfo(
        name=PLUGIN_NAME,
        description=PLUGIN_DESCRIPTION,
        system_prompt_extra=SYSTEM_PROMPT_CALENDAR,
    )

    registry.register(info, tools)
    registry.plugin_data[PLUGIN_DATA_CALENDAR_SERVICE] = service

    logger.info("Calendar plugin registered with %d tools", len(tools))
