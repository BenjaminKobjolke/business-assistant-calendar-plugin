"""Plugin-specific string constants."""

# Environment variable names
ENV_GOOGLE_CALENDAR_CREDENTIALS_PATH = "GOOGLE_CALENDAR_CREDENTIALS_PATH"
ENV_GOOGLE_CALENDAR_TOKEN_PATH = "GOOGLE_CALENDAR_TOKEN_PATH"
ENV_GOOGLE_CALENDAR_ID = "GOOGLE_CALENDAR_ID"
ENV_GOOGLE_CALENDAR_TIMEZONE = "GOOGLE_CALENDAR_TIMEZONE"
ENV_GOOGLE_CALENDAR_OAUTH_PORT = "GOOGLE_CALENDAR_OAUTH_PORT"
ENV_GOOGLE_CALENDAR_FREE_CHECK_IDS = "GOOGLE_CALENDAR_FREE_CHECK_IDS"

# Defaults
DEFAULT_TOKEN_PATH = "token.json"
DEFAULT_CALENDAR_ID = "primary"
DEFAULT_TIMEZONE = "Europe/Berlin"
DEFAULT_OAUTH_PORT = 51032

# Plugin name
PLUGIN_NAME = "calendar"
PLUGIN_DESCRIPTION = "Google Calendar operations"

# Plugin data key
PLUGIN_DATA_CALENDAR_SERVICE = "calendar_service"

# System prompt extra
SYSTEM_PROMPT_CALENDAR = """You have access to Google Calendar tools:
- list_calendars: List all available Google calendars (name, ID)
- list_events: List events for today or a date range (date_str, days)
- create_event: Create a timed event (summary, start, end, add_google_meet for Meet)
- create_all_day_event: Create an all-day event (summary, date_str YYYY-MM-DD)
- delete_event: Delete an event by Google Calendar event ID
- import_ics_event: Import ICS calendar data to Google Calendar
- find_conflicts: Check for conflicting events across configured calendars
- search_events: Search upcoming events by keyword

## Chaining with IMAP plugin

When the user wants to import a meeting invite from email to their calendar:
1. Use detect_invite (IMAP plugin) to get ICS data from the email
2. Use import_ics_event (this plugin) with the ICS data to add it to Google Calendar

## Creating events — IMPORTANT

When the user asks to create or add an event/date, follow this workflow strictly:

### Step 1: Show preview — DO NOT CREATE YET
- Parse the date/time and summarize what will be created
- Show: summary, date, time range (or "all-day")
- Ask: "Shall I add this to your calendar?"

### Step 2: Create — ONLY when the user explicitly confirms
- "yes" / "ja" / "do it" / "add it" → call create_event or create_all_day_event
- NEVER call create_event or create_all_day_event without explicit user confirmation

## Deleting events

When deleting events, first use list_events or search_events to find the event \
and confirm the correct event with the user before deleting."""
