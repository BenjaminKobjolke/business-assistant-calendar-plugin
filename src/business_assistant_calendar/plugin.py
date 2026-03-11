"""Plugin registration — defines PydanticAI tools for calendar operations."""

from __future__ import annotations

import logging
import threading
import wsgiref.simple_server
import wsgiref.util
from pathlib import Path

from business_assistant.agent.deps import Deps
from business_assistant.plugins.registry import PluginInfo, PluginRegistry
from pydantic_ai import RunContext, Tool

from .calendar_service import CalendarService
from .config import load_calendar_settings
from .constants import (
    PLUGIN_CATEGORY,
    PLUGIN_DATA_CALENDAR_AUTH_STATE,
    PLUGIN_DATA_CALENDAR_SERVICE,
    PLUGIN_DATA_CALENDAR_SETTINGS,
    PLUGIN_DESCRIPTION,
    PLUGIN_NAME,
    SYSTEM_PROMPT_CALENDAR,
    SYSTEM_PROMPT_CALENDAR_SETUP,
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
    add_google_meet: bool = False,
) -> str:
    """Create a timed event. Provide summary, start and end as ISO datetime strings.
    Set add_google_meet=True to attach a Google Meet video conference link.
    """
    return _get_service(ctx).create_event(
        summary, start, end, calendar_id, add_google_meet
    )


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


# --- Setup / Auth tools ---


def _calendar_start_auth(ctx: RunContext[Deps]) -> str:
    """Start Google Calendar OAuth and return the authorization URL."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    from .calendar_client import GoogleCalendarClient

    settings = ctx.deps.plugin_data[PLUGIN_DATA_CALENDAR_SETTINGS]
    flow = InstalledAppFlow.from_client_secrets_file(
        settings.credentials_path, GoogleCalendarClient.SCOPES
    )
    port = settings.oauth_port
    flow.redirect_uri = f"http://localhost:{port}/"
    auth_url, _ = flow.authorization_url(
        access_type="offline", prompt="consent"
    )

    auth_state = {
        "flow": flow,
        "response_uri": None,
        "done": threading.Event(),
        "token_path": settings.token_path,
    }

    class _QuietHandler(wsgiref.simple_server.WSGIRequestHandler):
        def log_message(self, format, *args):  # noqa: A002
            pass

    def _callback_app(environ, start_response):
        start_response("200 OK", [("Content-type", "text/html")])
        auth_state["response_uri"] = wsgiref.util.request_uri(environ)
        auth_state["done"].set()
        return [
            b"<html><body>Authorization complete. "
            b"You can close this window.</body></html>"
        ]

    def run_server():
        server = wsgiref.simple_server.make_server(
            "localhost", port, _callback_app, handler_class=_QuietHandler
        )
        server.timeout = 300
        server.handle_request()
        server.server_close()

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()

    ctx.deps.plugin_data[PLUGIN_DATA_CALENDAR_AUTH_STATE] = auth_state
    return (
        f"Open this URL to authorize Google Calendar:\n{auth_url}\n\n"
        "After you approve access in your browser, tell me and "
        "I'll complete the setup."
    )


def _calendar_complete_auth(ctx: RunContext[Deps]) -> str:
    """Complete Google Calendar authorization after user approved access."""
    auth_state = ctx.deps.plugin_data.get(PLUGIN_DATA_CALENDAR_AUTH_STATE)
    if auth_state is None:
        return "No pending authorization. Please start the setup first."

    if not auth_state["done"].is_set():
        return (
            "Authorization not yet received. "
            "Please open the URL in your browser and approve access first."
        )

    try:
        flow = auth_state["flow"]
        response_uri = auth_state["response_uri"]
        authorization_response = response_uri.replace("http", "https")
        flow.fetch_token(authorization_response=authorization_response)
        creds = flow.credentials

        token_path = Path(auth_state["token_path"])
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json())

        del ctx.deps.plugin_data[PLUGIN_DATA_CALENDAR_AUTH_STATE]
        return (
            "Google Calendar authorized! Token saved. "
            "Please fully stop and restart the bot to activate Calendar tools."
        )
    except Exception as exc:
        del ctx.deps.plugin_data[PLUGIN_DATA_CALENDAR_AUTH_STATE]
        return (
            f"Authorization failed: {exc}. "
            "Please try starting the auth again."
        )


def register(registry: PluginRegistry) -> None:
    """Register the calendar plugin with the plugin registry.

    Reads Google Calendar settings from environment. Skips registration
    if GOOGLE_CALENDAR_CREDENTIALS_PATH is not configured.
    """
    from business_assistant.config.log_setup import add_plugin_logging

    add_plugin_logging("calendar", "business_assistant_calendar")

    settings = load_calendar_settings()
    if settings is None:
        logger.info(
            "Calendar plugin: GOOGLE_CALENDAR_CREDENTIALS_PATH not configured, "
            "skipping registration"
        )
        return

    if not Path(settings.token_path).exists():
        logger.info(
            "Calendar plugin: token not found, registering setup tools"
        )
        registry.plugin_data[PLUGIN_DATA_CALENDAR_SETTINGS] = settings
        tools = [
            Tool(_calendar_start_auth, name="calendar_start_auth"),
            Tool(_calendar_complete_auth, name="calendar_complete_auth"),
        ]
        info = PluginInfo(
            name=PLUGIN_NAME,
            description=PLUGIN_DESCRIPTION,
            system_prompt_extra=SYSTEM_PROMPT_CALENDAR_SETUP,
            category=PLUGIN_CATEGORY,
        )
        registry.register(info, tools)
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
        category=PLUGIN_CATEGORY,
    )

    registry.register(info, tools)
    registry.plugin_data[PLUGIN_DATA_CALENDAR_SERVICE] = service

    logger.info("Calendar plugin registered with %d tools", len(tools))
