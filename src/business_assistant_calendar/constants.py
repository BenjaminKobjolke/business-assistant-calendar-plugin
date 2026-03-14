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

# Plugin name and category
PLUGIN_NAME = "calendar"
PLUGIN_CATEGORY = "calendar"
PLUGIN_DESCRIPTION = "Google Calendar operations"

# Plugin data keys
PLUGIN_DATA_CALENDAR_SERVICE = "calendar_service"
PLUGIN_DATA_CALENDAR_SETTINGS = "calendar_settings"
PLUGIN_DATA_CALENDAR_AUTH_STATE = "calendar_auth_state"

# System prompt extra
SYSTEM_PROMPT_CALENDAR = """You have access to Google Calendar tools:
- list_calendars: List all available Google calendars (name, ID)
- list_events: List events for today or a date range (date_str, days, calendar_id)
- create_event: Create a calendar event. For timed events: provide summary, start, \
end (ISO datetime). Set add_google_meet=True for a Meet link. For all-day events: \
set all_day=True and provide summary and date_str (YYYY-MM-DD).
- delete_event: Delete an event by Google Calendar event ID
- update_event: Update an existing event's fields (summary, location, description, start, end)
- import_ics_event: Import ICS calendar data to Google Calendar
- find_conflicts: Check for conflicting events across configured calendars
- search_events: Search upcoming events by keyword (query, days_ahead, calendar_id)

## Formatting — CRITICAL
- Listing tools (list_calendars, list_events, search_events, find_conflicts) \
return JSON. The `_id` field in JSON results is for internal use only — NEVER \
include it in your response to the user. Compose natural-language summaries from \
the other fields.
- NEVER include any internal IDs in your responses to the user. This includes:
  - Email message IDs (like [117250], 117250, msg_id)
  - Google Calendar event IDs
  - Any technical identifier
- IDs are for your internal use only. \
Never write "E-Mail-ID: 117250" or "[117250]" or similar in your response. \
Strip all IDs when presenting information to the user.

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
- "yes" / "ja" / "do it" / "add it" → call create_event (with all_day=True for \
all-day events)
- NEVER call create_event without explicit user confirmation

## All-day events — date range interpretation

All-day events in list_events/search_events include `start_date` and `end_date` fields.
- `end_date` is **exclusive** (Google Calendar convention): an event with \
`start_date: "2026-03-05"` and `end_date: "2026-03-13"` runs from March 5 \
through March 12 (last day is the day BEFORE end_date).
- A single-day all-day event has end_date = start_date + 1 day.
- When telling the user about event dates, always use the inclusive range \
(start_date through end_date minus 1 day).

## Today's agenda — filtering past events

When the user asks for today's events/appointments/agenda:
- After calling list_events, compare each event's end time to the current time.
- **Exclude** timed events whose end time is before now (they already happened).
- **Always keep** all-day events regardless of the current time.
- Do NOT mention the filtered-out events at all.

## Deleting events

When deleting events, first use list_events or search_events to find the event \
and confirm the correct event with the user before deleting.

## Updating events

Use update_event to modify existing event fields (location, description, summary, time).
First find the event via list_events or search_events, then update it by event_id.
Only provide the fields that need to change — omitted fields stay unchanged.

## Searching / listing in specific calendars

list_events and search_events default to the primary calendar. When the user mentions \
a specific calendar by name (e.g., "Privat", "Team"), first use list_calendars to find \
the calendar_id, then pass it to list_events or search_events."""

SYSTEM_PROMPT_CALENDAR_SETUP = """Google Calendar integration is available \
but not yet authenticated.

You have two setup tools:
- calendar_start_auth: Starts Google OAuth and returns the authorization URL.
- calendar_complete_auth: Completes authorization after the user approves in \
their browser.

When the user asks about calendar, events, or scheduling:
1. Tell them Google Calendar is available but needs a one-time authorization.
2. Offer to start — call calendar_start_auth and share the returned URL.
3. The user must open the URL in a browser that can reach this server's localhost.
4. After they confirm they authorized, call calendar_complete_auth.
5. Tell them the bot needs a full process restart to activate Calendar tools."""
