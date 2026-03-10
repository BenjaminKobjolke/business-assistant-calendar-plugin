"""Tests for CalendarService with mocked GoogleCalendarClient."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from business_assistant_calendar.calendar_service import CalendarService
from business_assistant_calendar.config import CalendarSettings
from tests.conftest import (
    SAMPLE_CALENDAR_LIST,
    SAMPLE_GOOGLE_EVENT,
    SAMPLE_GOOGLE_EVENT_ALL_DAY,
    SAMPLE_ICS,
)


class TestCalendarService:
    def _make_service(
        self, settings: CalendarSettings, mock_client: MagicMock
    ) -> CalendarService:
        """Create a service with a pre-injected mock client."""
        service = CalendarService(settings)
        service._client = mock_client
        return service

    def test_list_calendars(self, calendar_settings: CalendarSettings) -> None:
        mock_client = MagicMock()
        mock_client.list_calendars.return_value = SAMPLE_CALENDAR_LIST
        service = self._make_service(calendar_settings, mock_client)

        result = service.list_calendars()

        data = json.loads(result)
        assert len(data["calendars"]) == 2
        assert data["calendars"][0]["name"] == "My Calendar"
        assert data["calendars"][0]["primary"] is True
        assert data["calendars"][1]["name"] == "Team Calendar"
        assert data["calendars"][1]["_id"] == "team@group.calendar.google.com"

    def test_list_calendars_empty(self, calendar_settings: CalendarSettings) -> None:
        mock_client = MagicMock()
        mock_client.list_calendars.return_value = []
        service = self._make_service(calendar_settings, mock_client)

        result = service.list_calendars()

        assert "No calendars found" in result

    def test_list_events(self, calendar_settings: CalendarSettings) -> None:
        mock_client = MagicMock()
        mock_client.list_events_in_range.return_value = [
            SAMPLE_GOOGLE_EVENT,
            SAMPLE_GOOGLE_EVENT_ALL_DAY,
        ]
        service = self._make_service(calendar_settings, mock_client)

        result = service.list_events("2026-03-15", days=7)

        data = json.loads(result)
        assert len(data["events"]) == 2
        summaries = [e["summary"] for e in data["events"]]
        assert "Team Standup" in summaries
        assert "Company Holiday" in summaries
        assert data["events"][0]["_id"] == "evt_abc123"

    def test_list_events_no_events(self, calendar_settings: CalendarSettings) -> None:
        mock_client = MagicMock()
        mock_client.list_events_in_range.return_value = []
        service = self._make_service(calendar_settings, mock_client)

        result = service.list_events("2026-03-15")

        assert "No events found" in result

    def test_list_events_default_today(self, calendar_settings: CalendarSettings) -> None:
        mock_client = MagicMock()
        mock_client.list_events_in_range.return_value = []
        service = self._make_service(calendar_settings, mock_client)

        result = service.list_events()

        assert "No events found" in result
        mock_client.list_events_in_range.assert_called_once()

    def test_create_event(self, calendar_settings: CalendarSettings) -> None:
        mock_client = MagicMock()
        mock_client.create_event.return_value = ("evt_new123", "")
        service = self._make_service(calendar_settings, mock_client)

        result = service.create_event(
            "Sprint Planning",
            "2026-03-15T14:00:00",
            "2026-03-15T15:00:00",
        )

        assert "Event created" in result
        assert "Sprint Planning" in result
        assert "Google Meet" not in result

    def test_create_event_with_google_meet(
        self, calendar_settings: CalendarSettings
    ) -> None:
        mock_client = MagicMock()
        mock_client.create_event.return_value = (
            "evt_meet",
            "https://meet.google.com/abc-defg-hij",
        )
        service = self._make_service(calendar_settings, mock_client)

        result = service.create_event(
            "Team Meeting",
            "2026-03-15T11:00:00",
            "2026-03-15T12:00:00",
            add_google_meet=True,
        )

        assert "Event created" in result
        assert "Google Meet" in result
        assert "https://meet.google.com/abc-defg-hij" in result

    def test_create_event_failure(self, calendar_settings: CalendarSettings) -> None:
        mock_client = MagicMock()
        mock_client.create_event.return_value = (None, "")
        service = self._make_service(calendar_settings, mock_client)

        result = service.create_event(
            "Sprint Planning",
            "2026-03-15T14:00:00",
            "2026-03-15T15:00:00",
        )

        assert "Failed to create event" in result

    def test_create_all_day_event(self, calendar_settings: CalendarSettings) -> None:
        mock_client = MagicMock()
        mock_client.create_all_day_event.return_value = "evt_allday"
        service = self._make_service(calendar_settings, mock_client)

        result = service.create_all_day_event("Holiday", "2026-03-20")

        assert "All-day event created" in result
        assert "Holiday" in result

    def test_delete_event_success(self, calendar_settings: CalendarSettings) -> None:
        mock_client = MagicMock()
        mock_client.delete_event.return_value = True
        service = self._make_service(calendar_settings, mock_client)

        result = service.delete_event("evt_123")

        assert "deleted successfully" in result

    def test_delete_event_failure(self, calendar_settings: CalendarSettings) -> None:
        mock_client = MagicMock()
        mock_client.delete_event.return_value = False
        service = self._make_service(calendar_settings, mock_client)

        result = service.delete_event("evt_123")

        assert "Failed to delete" in result

    def test_import_ics_event_success(self, calendar_settings: CalendarSettings) -> None:
        mock_client = MagicMock()
        mock_client.add_event_from_ics.return_value = "evt_imported"
        service = self._make_service(calendar_settings, mock_client)

        result = service.import_ics_event(SAMPLE_ICS)

        assert "imported successfully" in result

    def test_import_ics_event_failure(self, calendar_settings: CalendarSettings) -> None:
        mock_client = MagicMock()
        mock_client.add_event_from_ics.return_value = None
        service = self._make_service(calendar_settings, mock_client)

        result = service.import_ics_event(SAMPLE_ICS)

        assert "Failed to import" in result

    def test_find_conflicts_with_conflicts(
        self, calendar_settings: CalendarSettings
    ) -> None:
        mock_client = MagicMock()
        mock_client.list_events_in_range.return_value = [SAMPLE_GOOGLE_EVENT]
        service = self._make_service(calendar_settings, mock_client)

        result = service.find_conflicts(
            "2026-03-15T09:00:00",
            "2026-03-15T12:00:00",
        )

        data = json.loads(result)
        assert len(data["conflicts"]) >= 1
        assert data["conflicts"][0]["summary"] == "Team Standup"

    def test_find_conflicts_no_conflicts(
        self, calendar_settings: CalendarSettings
    ) -> None:
        mock_client = MagicMock()
        mock_client.list_events_in_range.return_value = []
        service = self._make_service(calendar_settings, mock_client)

        result = service.find_conflicts(
            "2026-03-15T09:00:00",
            "2026-03-15T12:00:00",
        )

        assert "No conflicts found" in result

    def test_search_events_with_matches(
        self, calendar_settings: CalendarSettings
    ) -> None:
        mock_client = MagicMock()
        mock_client.list_events_in_range.return_value = [
            SAMPLE_GOOGLE_EVENT,
            SAMPLE_GOOGLE_EVENT_ALL_DAY,
        ]
        service = self._make_service(calendar_settings, mock_client)

        result = service.search_events("Standup")

        data = json.loads(result)
        assert len(data["results"]) == 1
        assert data["results"][0]["summary"] == "Team Standup"

    def test_search_events_no_matches(
        self, calendar_settings: CalendarSettings
    ) -> None:
        mock_client = MagicMock()
        mock_client.list_events_in_range.return_value = [SAMPLE_GOOGLE_EVENT]
        service = self._make_service(calendar_settings, mock_client)

        result = service.search_events("Nonexistent")

        assert "No upcoming events matching" in result
