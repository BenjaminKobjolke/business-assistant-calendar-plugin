"""Shared test fixtures for the calendar plugin."""

from __future__ import annotations

import pytest

from business_assistant_calendar.config import CalendarSettings

SAMPLE_ICS = """\
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//EN
METHOD:REQUEST
BEGIN:VEVENT
UID:test-uid-123@example.com
DTSTART;TZID=Europe/Berlin:20260315T100000
DTEND;TZID=Europe/Berlin:20260315T110000
SUMMARY:Team Standup
ORGANIZER;CN=Alice Smith:mailto:alice@example.com
LOCATION:Conference Room A
END:VEVENT
END:VCALENDAR"""

SAMPLE_GOOGLE_EVENT = {
    "id": "evt_abc123",
    "summary": "Team Standup",
    "start": {"dateTime": "2026-03-15T10:00:00+01:00"},
    "end": {"dateTime": "2026-03-15T11:00:00+01:00"},
    "location": "Conference Room A",
}

SAMPLE_GOOGLE_EVENT_ALL_DAY = {
    "id": "evt_allday456",
    "summary": "Company Holiday",
    "start": {"date": "2026-03-20"},
    "end": {"date": "2026-03-21"},
}

SAMPLE_CALENDAR_LIST = [
    {"id": "primary", "summary": "My Calendar", "primary": True},
    {"id": "team@group.calendar.google.com", "summary": "Team Calendar"},
]


@pytest.fixture()
def calendar_settings() -> CalendarSettings:
    return CalendarSettings(
        credentials_path="/tmp/test_credentials.json",
        token_path="/tmp/test_token.json",
        calendar_id="primary",
        timezone="Europe/Berlin",
        oauth_port=51032,
        free_check_calendar_ids=("team@group.calendar.google.com",),
    )
