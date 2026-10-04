from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from backend.auth_api import get_current_user
from backend.database.connection import get_connection

router = APIRouter(prefix="/api/sharing", tags=["Shared scheduling"])


class FindSlotsIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    emails: list[EmailStr] = Field(min_length=1, max_length=20)
    duration_minutes: int = Field(default=60, ge=15, le=480)
    window_start: datetime
    window_end: datetime


class ConfirmSlotIn(BaseModel):
    start: datetime


def _participants(connection, organizer_id, emails):
    normalized = sorted({str(e).lower() for e in emails})
    rows = connection.execute(
        "SELECT id,email,name FROM users WHERE LOWER(email)=ANY(%s)",
        (normalized,),
    ).fetchall()
    found = {r["email"].lower() for r in rows}
    missing = [e for e in normalized if e not in found]
    if missing:
        raise HTTPException(status_code=404, detail={"message": "Some people are not on DayFlow yet", "emails": missing})
    return [{"id": organizer_id}] + list(rows)


def _free_slots(connection, user_ids, start, end, duration):
    busy = connection.execute(
        """SELECT user_id,starts_at,ends_at FROM calendar_events
           WHERE user_id=ANY(%s) AND starts_at < %s AND ends_at > %s
           ORDER BY starts_at""",
        (user_ids, end, start),
    ).fetchall()
    step = timedelta(minutes=30)
    needed = timedelta(minutes=duration)
    cursor = start
    slots = []
    while cursor + needed <= end and len(slots) < 8:
        candidate_end = cursor + needed
        conflicts = sum(1 for b in busy if b["starts_at"] < candidate_end and b["ends_at"] > cursor)
        if conflicts == 0:
            slots.append({"start": cursor, "end": candidate_end, "available_users": len(user_ids)})
        cursor += step
    return slots


@router.get("/users")
def search_users(q: str, user=Depends(get_current_user)):
    term = q.strip()
    if len(term) < 2:
        return []
    with get_connection() as connection:
        return connection.execute(
            """SELECT id,name,email,mode FROM users
               WHERE id<>%s AND (name ILIKE %s OR email ILIKE %s)
               ORDER BY name LIMIT 8""",
            (user["id"], f"%{term}%", f"%{term}%"),
        ).fetchall()


@router.post("/find-slots")
def find_slots(body: FindSlotsIn, user=Depends(get_current_user)):
    if body.window_end <= body.window_start:
        raise HTTPException(status_code=400, detail="Meeting window must end after it starts")
    with get_connection() as connection:
        people = _participants(connection, user["id"], body.emails)
        ids = [p["id"] for p in people]
        slots = _free_slots(connection, ids, body.window_start, body.window_end, body.duration_minutes)
    return {"title": body.title, "participants": len(ids), "slots": slots}


@router.post("/meetings", status_code=201)
def create_meeting(body: FindSlotsIn, user=Depends(get_current_user)):
    if body.window_end <= body.window_start:
        raise HTTPException(status_code=400, detail="Meeting window must end after it starts")
    with get_connection() as connection:
        people = _participants(connection, user["id"], body.emails)
        meeting = connection.execute(
            """INSERT INTO meeting_invites(organizer_id,title,duration_minutes,window_start,window_end)
               VALUES(%s,%s,%s,%s,%s) RETURNING *""",
            (user["id"], body.title, body.duration_minutes, body.window_start, body.window_end),
        ).fetchone()
        for person in people[1:]:
            connection.execute(
                "INSERT INTO meeting_invitees(meeting_id,user_id) VALUES(%s,%s)",
                (meeting["id"], person["id"]),
            )
        connection.commit()
        slots = _free_slots(connection, [p["id"] for p in people], body.window_start, body.window_end, body.duration_minutes)
    return {"meeting": meeting, "slots": slots}


@router.post("/meetings/{meeting_id}/confirm")
def confirm_meeting(meeting_id: UUID, body: ConfirmSlotIn, user=Depends(get_current_user)):
    with get_connection() as connection:
        meeting = connection.execute(
            "SELECT * FROM meeting_invites WHERE id=%s AND organizer_id=%s",
            (meeting_id, user["id"]),
        ).fetchone()
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        end = body.start + timedelta(minutes=meeting["duration_minutes"])
        if body.start < meeting["window_start"] or end > meeting["window_end"]:
            raise HTTPException(status_code=400, detail="Selected time is outside the meeting window")
        invitees = connection.execute(
            "SELECT user_id FROM meeting_invitees WHERE meeting_id=%s", (meeting_id,)
        ).fetchall()
        ids = [user["id"]] + [x["user_id"] for x in invitees]
        if not _free_slots(connection, ids, body.start, end, meeting["duration_minutes"]):
            raise HTTPException(status_code=409, detail="That slot is no longer free for everyone")
        connection.execute(
            """UPDATE meeting_invites SET status='scheduled',selected_start=%s,selected_end=%s WHERE id=%s""",
            (body.start, end, meeting_id),
        )
        for uid in ids:
            connection.execute(
                """INSERT INTO calendar_events(user_id,title,event_type,starts_at,ends_at,flexibility,source,external_id)
                   VALUES(%s,%s,'Shared meeting',%s,%s,'fixed','dayflow-shared',%s)
                   ON CONFLICT DO NOTHING""",
                (uid, meeting["title"], body.start, end, str(meeting_id)),
            )
        connection.execute(
            "UPDATE meeting_invitees SET status='accepted' WHERE meeting_id=%s", (meeting_id,)
        )
        connection.commit()
    return {"id": meeting_id, "status": "scheduled", "start": body.start, "end": end}


@router.get("/meetings")
def my_meetings(user=Depends(get_current_user)):
    with get_connection() as connection:
        return connection.execute(
            """SELECT DISTINCT m.* FROM meeting_invites m
               LEFT JOIN meeting_invitees i ON i.meeting_id=m.id
               WHERE m.organizer_id=%s OR i.user_id=%s ORDER BY m.created_at DESC""",
            (user["id"], user["id"]),
        ).fetchall()
