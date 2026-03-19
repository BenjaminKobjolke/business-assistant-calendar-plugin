"""CalendarService — wraps GoogleCalendarClient for all calendar operations."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any

from dateutil import parser as dateutil_parser

from .calendar_client import GoogleCalendarClient
from .config import CalendarSettings

logger = logging.getLogger(__name__)


class CalendarService:
    """High-level calendar operations returning formatted strings for LLM consumption."""

    def __init__(self, settings: CalendarSettings) -> None:
        self._settings = settings
        self._client = GoogleCalendarClient(settings)

    def list_calendars(self) -> str:
        """List all available Google calendars."""
        calendars = self._client.list_calendars()
        if not calendars:
            return "No calendars found."

        items = []
        for cal in calendars:
            items.append({
                "_id": cal.get("id", ""),
                "name": cal.get("summary", "(unnamed)"),
                "primary": bool(cal.get("primary")),
            })
        return json.dumps({"calendars": items})

    def list_events(
        self,
        date_str: str | None = None,
        days: int = 1,
        calendar_id: str | None = None,
    ) -> str:
        """List events for a date range. Defaults to today."""
        try:
            start_date = dateutil_parser.parse(date_str).date() if date_str else date.today()

            start_dt = datetime(
                start_date.year, start_date.month, start_date.day, 0, 0, 0
            )
            end_dt = start_dt + timedelta(days=days)

            cal_id = calendar_id or self._settings.calendar_id
            events = self._client.list_events_in_range(cal_id, start_dt, end_dt)

            if not events:
                if days == 1:
                    return f"No events found for {start_date.isoformat()}."
                return (
                    f"No events found from {start_date.isoformat()} "
                    f"to {(start_date + timedelta(days=days)).isoformat()}."
                )

            items = [_format_event_dict(event) for event in events]
            return json.dumps({"events": items})
        except Exception as e:
            return f"Error listing events: {e}"

    def create_event(
        self,
        summary: str,
        start: str,
        end: str,
        calendar_id: str | None = None,
        add_google_meet: bool = False,
        reminders: list[dict[str, int | str]] | None = None,
    ) -> str:
        """Create a timed event. Parses flexible datetime strings."""
        try:
            start_dt = dateutil_parser.parse(start)
            end_dt = dateutil_parser.parse(end)

            event_id, meet_link = self._client.create_event(
                summary, start_dt, end_dt, calendar_id, add_google_meet,
                reminders,
            )
            lines = [
                f"Event created: '{summary}'",
                f"  From: {start_dt.strftime('%Y-%m-%d %H:%M')}",
                f"  To:   {end_dt.strftime('%Y-%m-%d %H:%M')}",
            ]
            if meet_link:
                lines.append(f"  Google Meet: {meet_link}")
            if reminders:
                for r in reminders:
                    lines.append(
                        f"  Reminder: {r.get('method', 'popup')} "
                        f"{r.get('minutes', 0)} min before"
                    )
            return "\n".join(lines)
        except Exception as e:
            cal_label = calendar_id or "primary"
            return f"Error creating event in calendar '{cal_label}': {e}"

    def create_all_day_event(
        self,
        summary: str,
        date_str: str,
        calendar_id: str | None = None,
        reminders: list[dict[str, int | str]] | None = None,
    ) -> str:
        """Create an all-day event."""
        try:
            event_date = dateutil_parser.parse(date_str).date()
            self._client.create_all_day_event(
                summary, event_date, calendar_id, reminders,
            )
            return (
                f"All-day event created: '{summary}'\n"
                f"  Date: {event_date.isoformat()}"
            )
        except Exception as e:
            cal_label = calendar_id or "primary"
            return f"Error creating all-day event in calendar '{cal_label}': {e}"

    def delete_event(self, event_id: str, calendar_id: str | None = None) -> str:
        """Delete an event by Google Calendar event ID."""
        try:
            self._client.delete_event(event_id, calendar_id)
        except Exception as e:
            cal_label = calendar_id or "primary"
            return f"Error deleting event in calendar '{cal_label}': {e}"
        return "Event deleted successfully."

    def update_event(
        self,
        event_id: str,
        calendar_id: str | None = None,
        summary: str | None = None,
        location: str | None = None,
        description: str | None = None,
        start: str | None = None,
        end: str | None = None,
        reminders: list[dict[str, int | str]] | None = None,
    ) -> str:
        """Update an existing event. Only provided fields are changed."""
        try:
            start_dt = dateutil_parser.parse(start) if start else None
            end_dt = dateutil_parser.parse(end) if end else None
            result = self._client.update_event(
                event_id,
                calendar_id=calendar_id,
                summary=summary,
                location=location,
                description=description,
                start_dt=start_dt,
                end_dt=end_dt,
                reminders=reminders,
            )
            updated_summary = result.get("summary", summary or event_id)
            return f"Event updated: '{updated_summary}'"
        except Exception as e:
            cal_label = calendar_id or "primary"
            return f"Error updating event in calendar '{cal_label}': {e}"

    def import_ics_event(
        self, ics_data: str, calendar_id: str | None = None
    ) -> str:
        """Import ICS calendar data to Google Calendar."""
        try:
            sanitized = ics_data.replace("\x00", "").replace("\ufffd", "")
            ics_bytes = sanitized.encode("utf-8")
            event_id = self._client.add_event_from_ics(ics_bytes, calendar_id)
            if event_id:
                return "Event imported successfully."
            return "Failed to import event from ICS data. No VEVENT found."
        except Exception as e:
            return f"Error importing ICS event: {e}"

    def find_conflicts(self, start: str, end: str) -> str:
        """Check for conflicting events across configured calendars."""
        try:
            start_dt = dateutil_parser.parse(start)
            end_dt = dateutil_parser.parse(end)

            # Check main calendar + all free_check calendars
            calendar_ids = [self._settings.calendar_id]
            for cid in self._settings.free_check_calendar_ids:
                if cid not in calendar_ids:
                    calendar_ids.append(cid)

            conflicts: list[dict[str, str]] = []
            for cal_id in calendar_ids:
                events = self._client.list_events_in_range(cal_id, start_dt, end_dt)
                for event in events:
                    conflicts.append({
                        "_id": event.get("id", ""),
                        "summary": event.get("summary", "(no title)"),
                        "start": event.get("start", {}).get(
                            "dateTime", event.get("start", {}).get("date", "")
                        ),
                        "end": event.get("end", {}).get(
                            "dateTime", event.get("end", {}).get("date", "")
                        ),
                        "calendar": cal_id,
                    })

            if not conflicts:
                return (
                    f"No conflicts found between "
                    f"{start_dt.strftime('%Y-%m-%d %H:%M')} and "
                    f"{end_dt.strftime('%Y-%m-%d %H:%M')}."
                )

            return json.dumps({"conflicts": conflicts})
        except Exception as e:
            return f"Error checking conflicts: {e}"

    def get_event_details(
        self, event_id: str, calendar_id: str | None = None
    ) -> str:
        """Get full details for a single event including attendees."""
        try:
            cal_id = calendar_id or self._settings.calendar_id
            event = self._client.get_event(event_id, cal_id)
            if event is None:
                return f"Event not found: {event_id}"

            result = _format_event_dict(event)

            description = event.get("description", "")
            if description:
                result["description"] = description

            organizer = event.get("organizer", {})
            if organizer:
                result["organizer"] = organizer.get(
                    "displayName", organizer.get("email", "")
                )

            attendees_raw = event.get("attendees", [])
            attendees = []
            for att in attendees_raw:
                name = att.get("displayName", att.get("email", ""))
                status = att.get("responseStatus", "")
                entry: dict[str, str] = {"name": name}
                if status:
                    entry["status"] = status
                attendees.append(entry)
            result["attendees"] = attendees

            reminders_data = event.get("reminders", {})
            overrides = reminders_data.get("overrides", [])
            if overrides:
                result["reminders"] = [
                    {"method": r.get("method", "popup"), "minutes": r.get("minutes", 0)}
                    for r in overrides
                ]

            return json.dumps({"event": result})
        except Exception as e:
            return f"Error getting event details: {e}"

    def search_events(
        self, query: str, days_ahead: int = 30, calendar_id: str | None = None,
    ) -> str:
        """Search upcoming events by keyword."""
        try:
            start_dt = datetime.now()
            end_dt = start_dt + timedelta(days=days_ahead)

            cal_id = calendar_id or self._settings.calendar_id
            events = self._client.list_events_in_range(cal_id, start_dt, end_dt)

            query_lower = query.lower()
            matches = []
            for event in events:
                summary = event.get("summary", "")
                description = event.get("description", "")
                location = event.get("location", "")
                searchable = f"{summary} {description} {location}".lower()
                if query_lower in searchable:
                    matches.append(event)

            if not matches:
                return f"No upcoming events matching '{query}' found."

            items = [_format_event_dict(event) for event in matches]
            return json.dumps({"results": items})
        except Exception as e:
            return f"Error searching events: {e}"


def _format_event_dict(event: dict) -> dict:
    """Format a single Google Calendar event as a dict for JSON output."""
    summary = event.get("summary", "(no title)")
    start = event.get("start", {})
    end = event.get("end", {})

    start_str = start.get("dateTime", start.get("date", ""))
    end_str = end.get("dateTime", end.get("date", ""))

    # Format datetime strings for readability
    is_all_day = "T" not in start_str and start_str != ""
    event_date = ""
    try:
        if "T" in start_str:
            start_dt = dateutil_parser.parse(start_str)
            start_display = start_dt.strftime("%H:%M")
            event_date = start_dt.strftime("%Y-%m-%d")
        else:
            start_display = "all-day"
    except Exception:
        start_display = start_str

    try:
        if "T" in end_str:
            end_dt = dateutil_parser.parse(end_str)
            end_display = end_dt.strftime("%H:%M")
        else:
            end_display = ""
    except Exception:
        end_display = end_str

    result: dict[str, Any] = {
        "_id": event.get("id", ""),
        "time": f"{start_display} - {end_display}" if end_display else start_display,
        "summary": summary,
    }

    # Include date for timed events so the AI knows which day the event falls on
    if not is_all_day and event_date:
        result["date"] = event_date

    # Include explicit date range for all-day events so the AI knows the span
    if is_all_day:
        result["start_date"] = start_str
        result["end_date"] = end_str

    location = event.get("location", "")
    if location:
        result["location"] = location

    reminders = event.get("reminders", {})
    overrides = reminders.get("overrides", [])
    if overrides:
        result["reminders"] = [
            {"method": r.get("method", "popup"), "minutes": r.get("minutes", 0)}
            for r in overrides
        ]

    return result
