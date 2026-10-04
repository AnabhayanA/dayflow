from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.auth_api import get_current_user
from backend.database.connection import get_connection

router = APIRouter(prefix="/api", tags=["Planner"])


class EventIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    start: datetime
    end: datetime
    event_type: str = "Personal"
    flexibility: str = "fixed"


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    category: str = "Personal"
    deadline: datetime | None = None
    estimated_minutes: int = Field(default=60, ge=5, le=1440)
    priority: str = "medium"
    flexibility: str = "flexible"


def owned(table: str, item_id: UUID, user_id: UUID):
    with get_connection() as connection:
        row = connection.execute(
            f"SELECT * FROM {table} WHERE id = %s AND user_id = %s",
            (item_id, user_id),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Item not found")
    return row


@router.get("/events")
def list_events(user=Depends(get_current_user)):
    with get_connection() as connection:
        return connection.execute(
            "SELECT id,title,event_type,starts_at,ends_at,flexibility,source FROM calendar_events WHERE user_id=%s ORDER BY starts_at",
            (user["id"],),
        ).fetchall()


@router.post("/events", status_code=201)
def create_event(body: EventIn, user=Depends(get_current_user)):
    if body.end <= body.start:
        raise HTTPException(status_code=400, detail="Event end must be after start")
    with get_connection() as connection:
        row = connection.execute(
            """
            INSERT INTO calendar_events(user_id,title,event_type,starts_at,ends_at,flexibility)
            VALUES(%s,%s,%s,%s,%s,%s)
            RETURNING *
            """,
            (user["id"], body.title, body.event_type, body.start, body.end, body.flexibility),
        ).fetchone()
        connection.commit()
    return row


@router.put("/events/{item_id}")
def update_event(item_id: UUID, body: EventIn, user=Depends(get_current_user)):
    owned("calendar_events", item_id, user["id"])
    if body.end <= body.start:
        raise HTTPException(status_code=400, detail="Event end must be after start")
    with get_connection() as connection:
        row = connection.execute(
            """
            UPDATE calendar_events SET title=%s,event_type=%s,starts_at=%s,ends_at=%s,flexibility=%s
            WHERE id=%s AND user_id=%s RETURNING *
            """,
            (body.title, body.event_type, body.start, body.end, body.flexibility, item_id, user["id"]),
        ).fetchone()
        connection.commit()
    return row


@router.delete("/events/{item_id}", status_code=204)
def delete_event(item_id: UUID, user=Depends(get_current_user)):
    owned("calendar_events", item_id, user["id"])
    with get_connection() as connection:
        connection.execute("DELETE FROM calendar_events WHERE id=%s AND user_id=%s", (item_id, user["id"]))
        connection.commit()


@router.get("/tasks")
def list_tasks(user=Depends(get_current_user)):
    with get_connection() as connection:
        return connection.execute(
            "SELECT * FROM tasks WHERE user_id=%s ORDER BY completed, deadline NULLS LAST, created_at",
            (user["id"],),
        ).fetchall()


@router.post("/tasks", status_code=201)
def create_task(body: TaskIn, user=Depends(get_current_user)):
    with get_connection() as connection:
        row = connection.execute(
            """
            INSERT INTO tasks(user_id,title,category,deadline,estimated_minutes,priority,flexibility)
            VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING *
            """,
            (user["id"], body.title, body.category, body.deadline, body.estimated_minutes, body.priority, body.flexibility),
        ).fetchone()
        connection.commit()
    return row


@router.put("/tasks/{item_id}")
def update_task(item_id: UUID, body: TaskIn, user=Depends(get_current_user)):
    owned("tasks", item_id, user["id"])
    with get_connection() as connection:
        row = connection.execute(
            """
            UPDATE tasks SET title=%s,category=%s,deadline=%s,estimated_minutes=%s,priority=%s,flexibility=%s,updated_at=NOW()
            WHERE id=%s AND user_id=%s RETURNING *
            """,
            (body.title, body.category, body.deadline, body.estimated_minutes, body.priority, body.flexibility, item_id, user["id"]),
        ).fetchone()
        connection.commit()
    return row


class TaskStatusIn(BaseModel):
    completed: bool


@router.patch("/tasks/{item_id}/status")
def set_task_status(item_id: UUID, body: TaskStatusIn, user=Depends(get_current_user)):
    owned("tasks", item_id, user["id"])
    with get_connection() as connection:
        row = connection.execute(
            "UPDATE tasks SET completed=%s,updated_at=NOW() WHERE id=%s AND user_id=%s RETURNING *",
            (body.completed, item_id, user["id"]),
        ).fetchone()
        connection.commit()
    return row


@router.get("/changes")
def list_changes(user=Depends(get_current_user)):
    with get_connection() as connection:
        return connection.execute(
            """SELECT id,reason,explanation,status,created_at FROM schedule_changes
               WHERE user_id=%s ORDER BY created_at DESC LIMIT 20""",
            (user["id"],),
        ).fetchall()


@router.delete("/tasks/{item_id}", status_code=204)
def delete_task(item_id: UUID, user=Depends(get_current_user)):
    owned("tasks", item_id, user["id"])
    with get_connection() as connection:
        connection.execute("DELETE FROM tasks WHERE id=%s AND user_id=%s", (item_id, user["id"]))
        connection.commit()
