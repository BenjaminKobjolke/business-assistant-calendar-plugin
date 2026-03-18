"""Tests for GoogleCalendarClient with mocked Google API."""

from __future__ import annotations

import ssl
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

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
        with pytest.raises(Exception, match="API error"):
            client.create_event("Test Meeting", start_dt, end_dt)

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

        client.delete_event("evt_123")  # should not raise

    def test_delete_event_failure(self, calendar_settings: CalendarSettings) -> None:
        mock_service = MagicMock()
        mock_service.events().delete().execute.side_effect = Exception("Not found")
        client = self._make_client(calendar_settings, mock_service)

        with pytest.raises(Exception, match="Not found"):
            client.delete_event("evt_123")

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

    def test_get_event_success(self, calendar_settings: CalendarSettings) -> None:
        mock_service = MagicMock()
        mock_service.events().get().execute.return_value = {
            "id": "evt_123",
            "summary": "Team Meeting",
            "attendees": [{"email": "alice@example.com", "displayName": "Alice"}],
        }
        client = self._make_client(calendar_settings, mock_service)

        result = client.get_event("evt_123")

        assert result is not None
        assert result["summary"] == "Team Meeting"

    def test_get_event_failure(self, calendar_settings: CalendarSettings) -> None:
        mock_service = MagicMock()
        mock_service.events().get().execute.side_effect = Exception("Not found")
        client = self._make_client(calendar_settings, mock_service)

        assert client.get_event("evt_missing") is None

    def test_update_event_success(self, calendar_settings: CalendarSettings) -> None:
        mock_service = MagicMock()
        mock_service.events().patch().execute.return_value = {
            "id": "evt_123",
            "summary": "Updated Meeting",
            "location": "Room B",
        }
        client = self._make_client(calendar_settings, mock_service)

        result = client.update_event(
            "evt_123", summary="Updated Meeting", location="Room B"
        )

        assert result is not None
        assert result["summary"] == "Updated Meeting"

    def test_update_event_failure(self, calendar_settings: CalendarSettings) -> None:
        mock_service = MagicMock()
        mock_service.events().patch().execute.side_effect = Exception("API error")
        client = self._make_client(calendar_settings, mock_service)

        with pytest.raises(Exception, match="API error"):
            client.update_event("evt_123", summary="Updated")

    def test_update_event_no_fields(self, calendar_settings: CalendarSettings) -> None:
        mock_service = MagicMock()
        mock_service.events().get().execute.return_value = {
            "id": "evt_123",
            "summary": "Original Meeting",
        }
        client = self._make_client(calendar_settings, mock_service)

        result = client.update_event("evt_123")

        assert result is not None
        assert result["summary"] == "Original Meeting"
        mock_service.events().patch.assert_not_called()

    def test_update_event_partial_fields(
        self, calendar_settings: CalendarSettings
    ) -> None:
        mock_service = MagicMock()
        mock_service.events().patch().execute.return_value = {
            "id": "evt_123",
            "summary": "Original",
            "location": "New Location",
        }
        client = self._make_client(calendar_settings, mock_service)

        result = client.update_event("evt_123", location="New Location")

        assert result is not None
        assert result["location"] == "New Location"

    def test_list_calendars_retries_on_ssl_error(
        self, calendar_settings: CalendarSettings,
    ) -> None:
        failing_service = MagicMock()
        failing_service.calendarList().list().execute.side_effect = ssl.SSLError(
            "WRONG_VERSION_NUMBER"
        )
        fresh_service = MagicMock()
        fresh_service.calendarList().list().execute.return_value = {
            "items": [{"id": "primary", "summary": "My Calendar"}],
        }
        client = GoogleCalendarClient(calendar_settings)
        client._get_service = MagicMock(side_effect=[failing_service, fresh_service])

        result = client.list_calendars()

        assert len(result) == 1
        assert result[0]["summary"] == "My Calendar"

    def test_create_event_resets_service_on_ssl_error(
        self, calendar_settings: CalendarSettings,
    ) -> None:
        mock_service = MagicMock()
        mock_service.events().insert().execute.side_effect = ssl.SSLError(
            "WRONG_VERSION_NUMBER"
        )
        client = self._make_client(calendar_settings, mock_service)

        start_dt = datetime(2026, 3, 15, 10, 0)
        end_dt = datetime(2026, 3, 15, 11, 0)
        with pytest.raises(ssl.SSLError):
            client.create_event("Test", start_dt, end_dt)

        assert client._service is None  # reset for next call

    def test_create_event_with_reminders(
        self, calendar_settings: CalendarSettings
    ) -> None:
        mock_service = MagicMock()
        mock_service.events().insert().execute.return_value = {"id": "evt_rem"}
        client = self._make_client(calendar_settings, mock_service)

        start_dt = datetime(2026, 3, 15, 10, 0)
        end_dt = datetime(2026, 3, 15, 11, 0)
        reminders = [{"method": "popup", "minutes": 30}]
        event_id, _ = client.create_event(
            "Reminder Meeting", start_dt, end_dt, reminders=reminders
        )

        assert event_id == "evt_rem"
        call_kwargs = mock_service.events().insert.call_args
        body = call_kwargs[1]["body"] if "body" in call_kwargs[1] else call_kwargs[0][0]
        assert body["reminders"] == {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": 30}],
        }

    def test_create_event_without_reminders_no_key(
        self, calendar_settings: CalendarSettings
    ) -> None:
        mock_service = MagicMock()
        mock_service.events().insert().execute.return_value = {"id": "evt_noremind"}
        client = self._make_client(calendar_settings, mock_service)

        start_dt = datetime(2026, 3, 15, 10, 0)
        end_dt = datetime(2026, 3, 15, 11, 0)
        client.create_event("No Reminder", start_dt, end_dt)

        call_kwargs = mock_service.events().insert.call_args
        body = call_kwargs[1]["body"] if "body" in call_kwargs[1] else call_kwargs[0][0]
        assert "reminders" not in body

    def test_create_all_day_event_with_reminders(
        self, calendar_settings: CalendarSettings
    ) -> None:
        mock_service = MagicMock()
        mock_service.events().insert().execute.return_value = {"id": "evt_allday_rem"}
        client = self._make_client(calendar_settings, mock_service)

        reminders = [{"method": "email", "minutes": 1440}]
        result = client.create_all_day_event(
            "Birthday", date(2026, 5, 24), reminders=reminders
        )

        assert result == "evt_allday_rem"
        call_kwargs = mock_service.events().insert.call_args
        body = call_kwargs[1]["body"] if "body" in call_kwargs[1] else call_kwargs[0][0]
        assert body["reminders"] == {
            "useDefault": False,
            "overrides": [{"method": "email", "minutes": 1440}],
        }

    def test_update_event_with_reminders(
        self, calendar_settings: CalendarSettings
    ) -> None:
        mock_service = MagicMock()
        mock_service.events().patch().execute.return_value = {
            "id": "evt_123",
            "summary": "Meeting",
        }
        client = self._make_client(calendar_settings, mock_service)

        reminders = [{"method": "popup", "minutes": 10080}]
        result = client.update_event("evt_123", reminders=reminders)

        assert result is not None
        call_kwargs = mock_service.events().patch.call_args
        body = call_kwargs[1]["body"] if "body" in call_kwargs[1] else call_kwargs[0][0]
        assert body["reminders"] == {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": 10080}],
        }


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

    def test_vevent_to_google_event_with_valarm(self) -> None:
        mock_alarm = MagicMock()
        mock_alarm.name = "VALARM"
        mock_trigger = MagicMock()
        mock_trigger.dt = -timedelta(minutes=30)
        mock_alarm.get.side_effect = lambda key, default=None: {
            "action": "DISPLAY",
            "trigger": mock_trigger,
        }.get(key, default)

        mock_vevent = MagicMock()
        mock_vevent.get.side_effect = lambda key: {
            "uid": "uid-alarm",
            "summary": "Alarm Event",
            "location": None,
            "description": None,
            "dtstart": None,
            "dtend": None,
            "organizer": None,
            "rrule": None,
        }.get(key)
        mock_vevent.subcomponents = [mock_alarm]

        result = vevent_to_google_event(mock_vevent)

        assert "reminders" in result
        assert result["reminders"]["useDefault"] is False
        assert len(result["reminders"]["overrides"]) == 1
        assert result["reminders"]["overrides"][0] == {
            "method": "popup",
            "minutes": 30,
        }

    def test_vevent_to_google_event_with_email_valarm(self) -> None:
        mock_alarm = MagicMock()
        mock_alarm.name = "VALARM"
        mock_trigger = MagicMock()
        mock_trigger.dt = -timedelta(days=1)
        mock_alarm.get.side_effect = lambda key, default=None: {
            "action": "EMAIL",
            "trigger": mock_trigger,
        }.get(key, default)

        mock_vevent = MagicMock()
        mock_vevent.get.side_effect = lambda key: {
            "uid": "uid-email-alarm",
            "summary": "Email Alarm Event",
            "location": None,
            "description": None,
            "dtstart": None,
            "dtend": None,
            "organizer": None,
            "rrule": None,
        }.get(key)
        mock_vevent.subcomponents = [mock_alarm]

        result = vevent_to_google_event(mock_vevent)

        assert result["reminders"]["overrides"][0] == {
            "method": "email",
            "minutes": 1440,
        }
