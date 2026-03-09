"""CalendarService — wraps GoogleCalendarClient for all calendar operations."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

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

        lines = [f"Available calendars ({len(calendars)}):"]
        for cal in calendars:
            name = cal.get("summary", "(unnamed)")
            cal_id = cal.get("id", "")
            primary = " (primary)" if cal.get("primary") else ""
            lines.append(f"  - {name}{primary} | ID: {cal_id}")
        return "\n".join(lines)

    def list_events(self, date_str: str | None = None, days: int = 1) -> str:
        """List events for a date range. Defaults to today."""
        try:
            start_date = dateutil_parser.parse(date_str).date() if date_str else date.today()

            start_dt = datetime(
                start_date.year, start_date.month, start_date.day, 0, 0, 0
            )
            end_dt = start_dt + timedelta(days=days)

            events = self._client.list_events_in_range(
                self._settings.calendar_id, start_dt, end_dt
            )

            if not events:
                if days == 1:
                    return f"No events found for {start_date.isoformat()}."
                return (
                    f"No events found from {start_date.isoformat()} "
                    f"to {(start_date + timedelta(days=days)).isoformat()}."
                )

            if days == 1:
                header = f"Events for {start_date.isoformat()} ({len(events)}):"
            else:
                end_date = start_date + timedelta(days=days)
                header = (
                    f"Events from {start_date.isoformat()} to "
                    f"{end_date.isoformat()} ({len(events)}):"
                )

            lines = [header]
            for event in events:
                lines.append(_format_event(event))
            return "\n".join(lines)
        except Exception as e:
            return f"Error listing events: {e}"

    def create_event(
        self,
        summary: str,
        start: str,
        end: str,
        calendar_id: str | None = None,
        add_google_meet: bool = False,
    ) -> str:
        """Create a timed event. Parses flexible datetime strings."""
        try:
            start_dt = dateutil_parser.parse(start)
            end_dt = dateutil_parser.parse(end)

            event_id, meet_link = self._client.create_event(
                summary, start_dt, end_dt, calendar_id, add_google_meet
            )
            if event_id:
                lines = [
                    f"Event created: '{summary}'",
                    f"  From: {start_dt.strftime('%Y-%m-%d %H:%M')}",
                    f"  To:   {end_dt.strftime('%Y-%m-%d %H:%M')}",
                ]
                if meet_link:
                    lines.append(f"  Google Meet: {meet_link}")
                return "\n".join(lines)
            return "Failed to create event."
        except Exception as e:
            return f"Error creating event: {e}"

    def create_all_day_event(
        self,
        summary: str,
        date_str: str,
        calendar_id: str | None = None,
    ) -> str:
        """Create an all-day event."""
        try:
            event_date = dateutil_parser.parse(date_str).date()
            event_id = self._client.create_all_day_event(
                summary, event_date, calendar_id
            )
            if event_id:
                return (
                    f"All-day event created: '{summary}'\n"
                    f"  Date: {event_date.isoformat()}"
                )
            return "Failed to create all-day event."
        except Exception as e:
            return f"Error creating all-day event: {e}"

    def delete_event(self, event_id: str, calendar_id: str | None = None) -> str:
        """Delete an event by Google Calendar event ID."""
        success = self._client.delete_event(event_id, calendar_id)
        if success:
            return f"Event {event_id} deleted successfully."
        return f"Failed to delete event {event_id}."

    def import_ics_event(
        self, ics_data: str, calendar_id: str | None = None
    ) -> str:
        """Import ICS calendar data to Google Calendar."""
        try:
            ics_bytes = ics_data.encode("utf-8")
            event_id = self._client.add_event_from_ics(ics_bytes, calendar_id)
            if event_id:
                return f"Event imported successfully. Event ID: {event_id}"
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

            conflicts: list[str] = []
            for cal_id in calendar_ids:
                events = self._client.list_events_in_range(cal_id, start_dt, end_dt)
                for event in events:
                    summary = event.get("summary", "(no title)")
                    event_start = event.get("start", {}).get(
                        "dateTime", event.get("start", {}).get("date", "")
                    )
                    event_end = event.get("end", {}).get(
                        "dateTime", event.get("end", {}).get("date", "")
                    )
                    conflicts.append(
                        f"  - {summary} ({event_start} — {event_end}) [calendar: {cal_id}]"
                    )

            if not conflicts:
                return (
                    f"No conflicts found between "
                    f"{start_dt.strftime('%Y-%m-%d %H:%M')} and "
                    f"{end_dt.strftime('%Y-%m-%d %H:%M')}."
                )

            lines = [
                f"Conflicts found ({len(conflicts)}) between "
                f"{start_dt.strftime('%Y-%m-%d %H:%M')} and "
                f"{end_dt.strftime('%Y-%m-%d %H:%M')}:"
            ]
            lines.extend(conflicts)
            return "\n".join(lines)
        except Exception as e:
            return f"Error checking conflicts: {e}"

    def search_events(self, query: str, days_ahead: int = 30) -> str:
        """Search upcoming events by keyword."""
        try:
            start_dt = datetime.now()
            end_dt = start_dt + timedelta(days=days_ahead)

            events = self._client.list_events_in_range(
                self._settings.calendar_id, start_dt, end_dt
            )

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

            lines = [f"Events matching '{query}' ({len(matches)} found):"]
            for event in matches:
                lines.append(_format_event(event))
            return "\n".join(lines)
        except Exception as e:
            return f"Error searching events: {e}"


def _format_event(event: dict) -> str:
    """Format a single Google Calendar event for display."""
    summary = event.get("summary", "(no title)")
    start = event.get("start", {})
    end = event.get("end", {})

    start_str = start.get("dateTime", start.get("date", ""))
    end_str = end.get("dateTime", end.get("date", ""))

    # Format datetime strings for readability
    try:
        if "T" in start_str:
            start_dt = dateutil_parser.parse(start_str)
            start_display = start_dt.strftime("%H:%M")
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

    time_display = f"{start_display} - {end_display}" if end_display else start_display

    location = event.get("location", "")
    event_id = event.get("id", "")

    line = f"  [{event_id}] {time_display} | {summary}"
    if location:
        line += f" | {location}"
    return line
