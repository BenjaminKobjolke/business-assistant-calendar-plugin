"""Tests for GoogleCalendarClient with mocked Google API."""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock, patch

from business_assistant_calendar.calendar_client import GoogleCalendarClient
from business_assistant_calendar.config import CalendarSettings
from business_assistant_calendar.vevent_converter import vevent_to_google_event
from tests.conftest import SAMPLE_ICS


class TestGoogleCalendarClient:
    def _make_client(
        self, settings: CalendarSettings, mock_service: MagicMock
    ) -> GoogleCalendarClient:
        """Create a client with a pre-injected mock service."""
        client = GoogleCalendarClient(settings)
        client._service = mock_service
        return client

    def test_test_connection_success(self, calendar_settings: CalendarSettings) -> None:
        mock_service = MagicMock()
        mock_service.calendarList().get().execute.return_value = {"id": "primary"}
        client = self._make_client(calendar_settings, mock_service)

        assert client.test_connection() is True

    def test_test_connection_failure(self, calendar_settings: CalendarSettings) -> None:
        mock_service = MagicMock()
        mock_service.calendarList().get().execute.side_effect = Exception("API error")
        client = self._make_client(calendar_settings, mock_service)

        assert client.test_connection() is False

    def test_list_calendars(self, calendar_settings: CalendarSettings) -> None:
        mock_service = MagicMock()
        mock_service.calendarList().list().execute.return_value = {
            "items": [
                {"id": "primary", "summary": "My Calendar"},
                {"id": "team@group", "summary": "Team"},
            ]
        }
        client = self._make_client(calendar_settings, mock_service)

        result = client.list_calendars()
        assert len(result) == 2
        assert result[0]["summary"] == "My Calendar"

    def test_list_calendars_empty(self, calendar_settings: CalendarSettings) -> None:
        mock_service = MagicMock()
        mock_service.calendarList().list().execute.return_value = {"items": []}
        client = self._make_client(calendar_settings, mock_service)

        assert client.list_calendars() == []

    def test_create_event(self, calendar_settings: CalendarSettings) -> None:
        mock_service = MagicMock()
        mock_service.events().insert().execute.return_value = {"id": "evt_new"}
        client = self._make_client(calendar_settings, mock_service)

        start_dt = datetime(2026, 3, 15, 10, 0)
        end_dt = datetime(2026, 3, 15, 11, 0)
        event_id, meet_link = client.create_event("Test Meeting", start_dt, end_dt)

        assert event_id == "evt_new"
        assert meet_link == ""

    def test_create_event_with_google_meet(
        self, calendar_settings: CalendarSettings
    ) -> None:
        mock_service = MagicMock()
        mock_service.events().insert().execute.return_value = {
            "id": "evt_meet",
            "conferenceData": {
                "entryPoints": [
                    {
                        "entryPointType": "video",
                        "uri": "https://meet.google.com/abc-defg-hij",
                    }
                ]
            },
        }
        client = self._make_client(calendar_settings, mock_service)

        start_dt = datetime(2026, 3, 15, 10, 0)
        end_dt = datetime(2026, 3, 15, 11, 0)
        event_id, meet_link = client.create_event(
            "Team Meeting", start_dt, end_dt, add_google_meet=True
        )

        assert event_id == "evt_meet"
        assert meet_link == "https://meet.google.com/abc-defg-hij"

    def test_create_event_failure(self, calendar_settings: CalendarSettings) -> None:
        mock_service = MagicMock()
        mock_service.events().insert().execute.side_effect = Exception("API error")
        client = self._make_client(calendar_settings, mock_service)

        start_dt = datetime(2026, 3, 15, 10, 0)
        end_dt = datetime(2026, 3, 15, 11, 0)
        event_id, meet_link = client.create_event("Test Meeting", start_dt, end_dt)

        assert event_id is None
        assert meet_link == ""

    def test_create_all_day_event(self, calendar_settings: CalendarSettings) -> None:
        mock_service = MagicMock()
        mock_service.events().insert().execute.return_value = {"id": "evt_allday"}
        client = self._make_client(calendar_settings, mock_service)

        result = client.create_all_day_event("Holiday", date(2026, 3, 20))

        assert result == "evt_allday"

    def test_delete_event(self, calendar_settings: CalendarSettings) -> None:
        mock_service = MagicMock()
        mock_service.events().delete().execute.return_value = None
        client = self._make_client(calendar_settings, mock_service)

        assert client.delete_event("evt_123") is True

    def test_delete_event_failure(self, calendar_settings: CalendarSettings) -> None:
        mock_service = MagicMock()
        mock_service.events().delete().execute.side_effect = Exception("Not found")
        client = self._make_client(calendar_settings, mock_service)

        assert client.delete_event("evt_123") is False

    def test_event_exists_by_uid(self, calendar_settings: CalendarSettings) -> None:
        mock_service = MagicMock()
        mock_service.events().list().execute.return_value = {
            "items": [{"id": "evt_found", "summary": "Meeting"}]
        }
        client = self._make_client(calendar_settings, mock_service)

        assert client.event_exists("uid-123", "Meeting", None) is True

    def test_event_exists_not_found(self, calendar_settings: CalendarSettings) -> None:
        mock_service = MagicMock()
        mock_service.events().list().execute.return_value = {"items": []}
        client = self._make_client(calendar_settings, mock_service)

        assert client.event_exists("uid-missing", "Meeting", None) is False

    @patch("icalendar.Calendar")
    def test_add_event_from_ics(
        self, mock_calendar_cls: MagicMock, calendar_settings: CalendarSettings
    ) -> None:
        mock_service = MagicMock()
        mock_service.events().import_().execute.return_value = {"id": "evt_imported"}

        # Create a mock VEVENT component
        mock_vevent = MagicMock()
        mock_vevent.name = "VEVENT"
        mock_vevent.get.side_effect = lambda key: {
            "uid": "test-uid-123",
            "summary": "Team Standup",
        }.get(key)

        mock_cal = MagicMock()
        mock_cal.walk.return_value = [mock_vevent]
        mock_calendar_cls.from_ical.return_value = mock_cal

        client = self._make_client(calendar_settings, mock_service)
        result = client.add_event_from_ics(SAMPLE_ICS.encode("utf-8"))

        assert result == "evt_imported"

    @patch("icalendar.Calendar")
    def test_add_event_from_ics_import_fallback(
        self, mock_calendar_cls: MagicMock, calendar_settings: CalendarSettings
    ) -> None:
        mock_service = MagicMock()
        mock_service.events().import_().execute.side_effect = Exception("import failed")
        mock_service.events().insert().execute.return_value = {"id": "evt_inserted"}

        mock_vevent = MagicMock()
        mock_vevent.name = "VEVENT"
        mock_vevent.get.side_effect = lambda key: {
            "uid": "test-uid-123",
            "summary": "Team Standup",
        }.get(key)

        mock_cal = MagicMock()
        mock_cal.walk.return_value = [mock_vevent]
        mock_calendar_cls.from_ical.return_value = mock_cal

        client = self._make_client(calendar_settings, mock_service)
        result = client.add_event_from_ics(SAMPLE_ICS.encode("utf-8"))

        assert result == "evt_inserted"

    def test_list_events_in_range(self, calendar_settings: CalendarSettings) -> None:
        mock_service = MagicMock()
        mock_service.events().list().execute.return_value = {
            "items": [
                {"id": "evt_1", "summary": "Meeting 1"},
                {"id": "evt_2", "summary": "Meeting 2"},
            ]
        }
        client = self._make_client(calendar_settings, mock_service)

        result = client.list_events_in_range(
            "primary",
            datetime(2026, 3, 15, 0, 0),
            datetime(2026, 3, 16, 0, 0),
        )

        assert len(result) == 2
        assert result[0]["summary"] == "Meeting 1"


class TestVeventConversion:
    def test_vevent_to_google_event_basic(self) -> None:
        mock_vevent = MagicMock()
        mock_vevent.get.side_effect = lambda key: {
            "uid": "uid-123",
            "summary": "Test Event",
            "location": "Room A",
            "description": "A test event",
            "dtstart": None,
            "dtend": None,
            "organizer": None,
            "rrule": None,
        }.get(key)

        result = vevent_to_google_event(mock_vevent)

        assert result["iCalUID"] == "uid-123"
        assert result["summary"] == "Test Event"
        assert result["location"] == "Room A"
        assert result["description"] == "A test event"

    def test_vevent_to_google_event_with_datetime(self) -> None:
        mock_dtstart = MagicMock()
        mock_dtstart.dt = datetime(2026, 3, 15, 10, 0, 0)

        mock_dtend = MagicMock()
        mock_dtend.dt = datetime(2026, 3, 15, 11, 0, 0)

        mock_vevent = MagicMock()
        mock_vevent.get.side_effect = lambda key: {
            "uid": "uid-456",
            "summary": "Timed Event",
            "location": None,
            "description": None,
            "dtstart": mock_dtstart,
            "dtend": mock_dtend,
            "organizer": None,
            "rrule": None,
        }.get(key)

        result = vevent_to_google_event(mock_vevent)

        assert "dateTime" in result["start"]
        assert "dateTime" in result["end"]

    def test_vevent_to_google_event_with_date(self) -> None:
        mock_dtstart = MagicMock()
        mock_dtstart.dt = date(2026, 3, 20)

        mock_dtend = MagicMock()
        mock_dtend.dt = date(2026, 3, 21)

        mock_vevent = MagicMock()
        mock_vevent.get.side_effect = lambda key: {
            "uid": "uid-789",
            "summary": "All Day Event",
            "location": None,
            "description": None,
            "dtstart": mock_dtstart,
            "dtend": mock_dtend,
            "organizer": None,
            "rrule": None,
        }.get(key)

        result = vevent_to_google_event(mock_vevent)

        assert "date" in result["start"]
        assert "date" in result["end"]
