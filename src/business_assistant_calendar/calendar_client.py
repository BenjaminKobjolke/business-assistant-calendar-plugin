"""Google Calendar API client with OAuth2 authentication."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import ClassVar

from .config import CalendarSettings

logger = logging.getLogger(__name__)


class GoogleCalendarClient:
    """Wraps the Google Calendar API with OAuth2 auth and event operations."""

    SCOPES: ClassVar[list[str]] = ["https://www.googleapis.com/auth/calendar"]

    def __init__(self, settings: CalendarSettings) -> None:
        """Initialize with CalendarSettings."""
        self._settings = settings
        self._credentials_path = Path(settings.credentials_path)
        self._token_path = Path(settings.token_path)
        self._service = None

    def _get_service(self):
        """Lazy-init Google Calendar API service with OAuth2."""
        if self._service is not None:
            return self._service

        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        creds: Credentials | None = None

        if self._token_path.exists():
            creds = Credentials.from_authorized_user_file(
                str(self._token_path), self.SCOPES
            )

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    logger.warning("Token refresh failed, re-authenticating")
                    creds = None

            if not creds:
                if not self._credentials_path.exists():
                    logger.error(
                        "Google Calendar credentials file not found: %s. "
                        "Download it from Google Cloud Console.",
                        self._credentials_path,
                    )
                    msg = f"Credentials file not found: {self._credentials_path}"
                    raise FileNotFoundError(msg)
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self._credentials_path), self.SCOPES
                )
                creds = flow.run_local_server(port=self._settings.oauth_port)

            self._token_path.write_text(creds.to_json())

        self._service = build("calendar", "v3", credentials=creds)
        return self._service

    def test_connection(self) -> bool:
        """Test the Google Calendar API connection."""
        try:
            service = self._get_service()
            service.calendarList().get(
                calendarId=self._settings.calendar_id
            ).execute()
            logger.info("Google Calendar connection test successful")
            return True
        except Exception as e:
            logger.error("Google Calendar connection test failed: %s", e)
            return False

    def list_calendars(self) -> list[dict]:
        """Fetch all calendars visible to the authenticated user."""
        try:
            service = self._get_service()
            result = service.calendarList().list().execute()
            return result.get("items", [])
        except Exception as e:
            logger.error("Failed to list calendars: %s", e)
            return []

    def list_events_in_range(
        self, calendar_id: str, time_min: datetime, time_max: datetime
    ) -> list[dict]:
        """List events from a calendar within a time range."""
        try:
            service = self._get_service()
            min_dt = time_min
            max_dt = time_max
            if min_dt.tzinfo is not None:
                min_dt = min_dt.astimezone(UTC).replace(tzinfo=None)
                max_dt = max_dt.astimezone(UTC).replace(tzinfo=None)
            results = service.events().list(
                calendarId=calendar_id,
                timeMin=f"{min_dt.isoformat()}Z",
                timeMax=f"{max_dt.isoformat()}Z",
                singleEvents=True,
                orderBy="startTime",
                showDeleted=False,
            ).execute()
            return results.get("items", [])
        except Exception as e:
            logger.error("Error listing events in range for %s: %s", calendar_id, e)
            return []

    def create_event(
        self,
        summary: str,
        start_dt: datetime,
        end_dt: datetime,
        calendar_id: str | None = None,
        add_google_meet: bool = False,
    ) -> tuple[str | None, str]:
        """Create a calendar event. Returns (event_id, meet_link)."""
        try:
            service = self._get_service()
            cal_id = calendar_id or self._settings.calendar_id
            timezone = self._settings.timezone
            event_body: dict = {
                "summary": summary,
                "start": {"dateTime": start_dt.isoformat(), "timeZone": timezone},
                "end": {"dateTime": end_dt.isoformat(), "timeZone": timezone},
            }

            conference_version = 0
            if add_google_meet:
                event_body["conferenceData"] = {
                    "createRequest": {"requestId": f"meet-{uuid.uuid4().hex}"}
                }
                conference_version = 1

            result = service.events().insert(
                calendarId=cal_id,
                body=event_body,
                sendUpdates="none",
                conferenceDataVersion=conference_version,
            ).execute()
            event_id = result.get("id")
            meet_link = ""
            if add_google_meet:
                entry_points = (
                    result.get("conferenceData", {}).get("entryPoints", [])
                )
                for ep in entry_points:
                    if ep.get("entryPointType") == "video":
                        meet_link = ep.get("uri", "")
                        break
            logger.info("Event created in Google Calendar, id=%s", event_id)
            return event_id, meet_link
        except Exception as e:
            logger.error("Failed to create event in Google Calendar: %s", e)
            return None, ""

    def create_all_day_event(
        self,
        summary: str,
        event_date: date,
        calendar_id: str | None = None,
    ) -> str | None:
        """Create an all-day event. Returns Google Calendar event ID or None."""
        try:
            service = self._get_service()
            cal_id = calendar_id or self._settings.calendar_id
            next_day = event_date + timedelta(days=1)
            event_body = {
                "summary": summary,
                "start": {"date": event_date.isoformat()},
                "end": {"date": next_day.isoformat()},
            }
            result = service.events().insert(
                calendarId=cal_id, body=event_body, sendUpdates="none"
            ).execute()
            event_id = result.get("id")
            logger.info("All-day event created in Google Calendar, id=%s", event_id)
            return event_id
        except Exception as e:
            logger.error("Failed to create all-day event in Google Calendar: %s", e)
            return None

    def add_event_from_ics(
        self, ics_data: bytes, calendar_id: str | None = None
    ) -> str | None:
        """Import an event from raw ICS data. Returns event ID or None."""
        try:
            from icalendar import Calendar

            service = self._get_service()
            cal_id = calendar_id or self._settings.calendar_id
            cal = Calendar.from_ical(ics_data)

            for component in cal.walk():
                if component.name != "VEVENT":
                    continue

                event_body = self._vevent_to_google_event(component)
                try:
                    result = service.events().import_(
                        calendarId=cal_id, body=event_body
                    ).execute()
                except Exception:
                    logger.debug("import_() failed, falling back to insert()")
                    insert_body = {
                        k: v for k, v in event_body.items() if k != "iCalUID"
                    }
                    result = service.events().insert(
                        calendarId=cal_id, body=insert_body, sendUpdates="none"
                    ).execute()
                event_id = result.get("id")
                logger.info("Event imported to Google Calendar, id=%s", event_id)
                return event_id

            logger.warning("No VEVENT found in ICS data")
            return None
        except Exception as e:
            logger.error("Failed to import event to Google Calendar: %s", e)
            return None

    def delete_event(self, event_id: str, calendar_id: str | None = None) -> bool:
        """Delete a calendar event by its Google Calendar event ID."""
        try:
            service = self._get_service()
            cal_id = calendar_id or self._settings.calendar_id
            service.events().delete(
                calendarId=cal_id, eventId=event_id
            ).execute()
            logger.info("Deleted event from Google Calendar, id=%s", event_id)
            return True
        except Exception as e:
            logger.error("Failed to delete event by ID: %s", e)
            return False

    def event_exists(
        self, uid: str | None, summary: str, start_time: datetime | None
    ) -> bool:
        """Check whether an event already exists (by UID or summary+time)."""
        if uid:
            found = self._find_event_by_uid(uid)
            if found:
                return True

        if start_time:
            found = self._find_event_by_summary_and_time(summary, start_time)
            if found:
                return True

        return False

    def _find_event_by_uid(self, uid: str) -> dict | None:
        """Search for an event by its iCalendar UID."""
        try:
            service = self._get_service()
            results = service.events().list(
                calendarId=self._settings.calendar_id,
                iCalUID=uid,
                showDeleted=False,
            ).execute()
            items = results.get("items", [])
            return items[0] if items else None
        except Exception as e:
            logger.error("Error searching for event by UID: %s", e)
            return None

    def _find_event_by_summary_and_time(
        self, summary: str, start_time: datetime
    ) -> dict | None:
        """Fallback duplicate detection by summary and start time window."""
        try:
            service = self._get_service()
            dt_min = start_time - timedelta(minutes=5)
            dt_max = start_time + timedelta(minutes=5)
            if dt_min.tzinfo is not None:
                dt_min = dt_min.astimezone(UTC).replace(tzinfo=None)
                dt_max = dt_max.astimezone(UTC).replace(tzinfo=None)
            time_min = dt_min.isoformat() + "Z"
            time_max = dt_max.isoformat() + "Z"
            results = service.events().list(
                calendarId=self._settings.calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                q=summary,
                showDeleted=False,
            ).execute()
            items = results.get("items", [])
            return items[0] if items else None
        except Exception as e:
            logger.error("Error searching for event by summary and time: %s", e)
            return None

    @staticmethod
    def _vevent_to_google_event(vevent) -> dict:
        """Convert an icalendar VEVENT component to a Google Calendar event body."""
        event: dict = {}

        uid = vevent.get("uid")
        if uid:
            event["iCalUID"] = str(uid)

        summary = vevent.get("summary")
        if summary:
            event["summary"] = str(summary)

        location = vevent.get("location")
        if location:
            event["location"] = str(location)

        description = vevent.get("description")
        if description:
            event["description"] = str(description)

        dtstart = vevent.get("dtstart")
        if dtstart:
            dt = dtstart.dt
            if isinstance(dt, datetime):
                event["start"] = {"dateTime": dt.isoformat(), "timeZone": "UTC"}
            else:
                event["start"] = {"date": dt.isoformat()}

        dtend = vevent.get("dtend")
        if dtend:
            dt = dtend.dt
            if isinstance(dt, datetime):
                event["end"] = {"dateTime": dt.isoformat(), "timeZone": "UTC"}
            else:
                event["end"] = {"date": dt.isoformat()}

        organizer = vevent.get("organizer")
        if organizer:
            org_email = str(organizer).replace("mailto:", "").replace("MAILTO:", "")
            cn = (
                organizer.params.get("CN", "")
                if hasattr(organizer, "params")
                else ""
            )
            event["organizer"] = {"email": org_email}
            if cn:
                event["organizer"]["displayName"] = str(cn)

        rrule = vevent.get("rrule")
        if rrule:
            event["recurrence"] = [f"RRULE:{rrule.to_ical().decode()}"]

        return event
