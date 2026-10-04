import json

from fastapi import HTTPException
from psycopg.types.json import Jsonb

from backend.calendar_api import create_google_event, delete_google_event, update_google_event
from backend.database.connection import get_connection
from backend.automation.conflicts import find_conflict


def _event(user_id, event_id):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM calendar_events WHERE id=%s AND user_id=%s", (event_id, user_id)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Calendar event not found")
    return row


def _audit(connection, user_id, reason, before, after):
    connection.execute(
        """INSERT INTO schedule_changes(user_id,reason,explanation,status,before_state,after_state)
           VALUES(%s,%s,%s,'applied',%s,%s)""",
        (user_id, reason, "Approved by the user in Tempo.",
         Jsonb(before, dumps=lambda obj: json.dumps(obj, default=str)),
         Jsonb(after, dumps=lambda obj: json.dumps(obj, default=str))),
    )


def execute_calendar_action(user_id, action):
    if action.type not in {"create_event", "update_event", "delete_event"}:
        raise HTTPException(status_code=400, detail="Unsupported Tempo action")

    if action.type in {"create_event", "update_event"}:
        if not action.title or not action.start or not action.end:
            raise HTTPException(status_code=400, detail="Tempo action is missing event details")
        if action.end <= action.start:
            raise HTTPException(status_code=400, detail="Event end must be after start")

    before, after = {}, {}

    if action.type == "create_event":
        clash = find_conflict(user_id, action.start, action.end)
        if clash:
            raise HTTPException(status_code=409, detail=f"That time now conflicts with {clash['title']}. Ask Tempo for another time.")
        google_event = create_google_event(user_id, action.title, action.start, action.end)
        source = "google" if google_event else "dayflow"
        external_id = google_event.get("id") if google_event else None
        with get_connection() as connection:
            row = connection.execute(
                """INSERT INTO calendar_events
                   (user_id,title,event_type,starts_at,ends_at,flexibility,source,external_id)
                   VALUES(%s,%s,%s,%s,%s,'fixed',%s,%s) RETURNING *""",
                (user_id, action.title, action.event_type, action.start, action.end, source, external_id),
            ).fetchone()
            after = dict(row)
            _audit(connection, user_id, f"Tempo created {action.title}", before, after)
            connection.commit()

    elif action.type == "update_event":
        if not action.event_id:
            raise HTTPException(status_code=400, detail="Tempo action is missing the event ID")
        existing = _event(user_id, action.event_id)
        clash = find_conflict(user_id, action.start, action.end, action.event_id)
        if clash:
            raise HTTPException(status_code=409, detail=f"That move now conflicts with {clash['title']}. Ask Tempo for another time.")
        before = dict(existing)
        if existing["source"] == "google":
            update_google_event(user_id, existing["external_id"], action.title, action.start, action.end)
        with get_connection() as connection:
            row = connection.execute(
                """UPDATE calendar_events SET title=%s,event_type=%s,starts_at=%s,ends_at=%s
                   WHERE id=%s AND user_id=%s RETURNING *""",
                (action.title, action.event_type, action.start, action.end, action.event_id, user_id),
            ).fetchone()
            after = dict(row)
            _audit(connection, user_id, f"Tempo moved {action.title}", before, after)
            connection.commit()

    else:
        if not action.event_id:
            raise HTTPException(status_code=400, detail="Tempo action is missing the event ID")
        existing = _event(user_id, action.event_id)
        before = dict(existing)
        if existing["source"] == "google":
            delete_google_event(user_id, existing["external_id"])
        with get_connection() as connection:
            connection.execute("DELETE FROM calendar_events WHERE id=%s AND user_id=%s", (action.event_id, user_id))
            _audit(connection, user_id, f"Tempo deleted {existing['title']}", before, after)
            connection.commit()

    return {"ok": True, "action": action.type, "event": after or before}
