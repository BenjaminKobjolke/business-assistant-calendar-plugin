"""Convert iCalendar VEVENT components to Google Calendar event bodies."""

from __future__ import annotations

from datetime import datetime


def vevent_to_google_event(vevent) -> dict:
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
