import os
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.auth_api import get_current_user
from backend.database.connection import get_connection

router = APIRouter(prefix="/api/ai", tags=["Tempo AI"])

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"

class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)

def compact_schedule(user_id):
    with get_connection() as connection:
        events = connection.execute(
            """SELECT title,event_type,starts_at,ends_at,flexibility,source
               FROM calendar_events WHERE user_id=%s AND ends_at >= NOW() - INTERVAL '1 day'
               ORDER BY starts_at LIMIT 80""", (user_id,)
        ).fetchall()
        tasks = connection.execute(
            """SELECT title,category,deadline,estimated_minutes,priority,completed,flexibility
               FROM tasks WHERE user_id=%s AND completed=FALSE
               ORDER BY CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                        deadline NULLS LAST LIMIT 50""", (user_id,)
        ).fetchall()
    return events, tasks

def line_event(e):
    return f"- {e['title']} | {e['starts_at']} to {e['ends_at']} | {e['event_type']} | {e['flexibility']} | {e['source']}"

def line_task(t):
    return f"- {t['title']} | {t['category']} | priority={t['priority']} | estimate={t['estimated_minutes']} min | deadline={t['deadline']} | {t['flexibility']}"

@router.post("/chat")
def chat(body: ChatIn, user=Depends(get_current_user)):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY is not configured")

    events, tasks = compact_schedule(user["id"])
    now = datetime.now(timezone.utc).isoformat()
    prompt = f"""You are Tempo, an AI personal secretary and scheduling assistant.
You are speaking to {user['name']} whose mode is {user['mode']}.
Current UTC time: {now}

Rules:
- Be concise, practical, warm, and decisive. Do not sound like a generic chatbot.
- Use ONLY the schedule/task context below for claims about this user's calendar. Never invent events, deadlines, free time, or commitments.
- Treat fixed/calendar events as protected. Never suggest moving classes, meetings, work shifts, or other fixed commitments unless the user explicitly asks.
- Protect high-priority tasks before medium/low-priority tasks.
- When asked to find time, reason around the listed event start/end times and give concrete candidate windows. State when the available context is insufficient.
- Do not claim that you created, moved, or deleted anything. This chat endpoint currently advises and proposes; actual changes require explicit user approval through Tempo.
- For destructive or significant schedule changes, clearly ask for confirmation first.
- If the user asks for something unrelated to scheduling/productivity, you may answer briefly but steer back to their goal when useful.
- Keep most answers under 180 words. Use bullets only when they improve clarity.

UPCOMING EVENTS:
{chr(10).join(line_event(e) for e in events) or "- No upcoming events in Tempo."}

OPEN TASKS:
{chr(10).join(line_task(t) for t in tasks) or "- No open tasks in Tempo."}

USER MESSAGE:
{body.message}
"""
    try:
        response = httpx.post(
            GEMINI_URL,
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            json={
                "model": "gemini-3.8-flash",
                "input": prompt,
                "generation_config": {"thinking_level": "low", "temperature": 0.35},
            },
            timeout=45,
        )
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="Could not reach Gemini") from None

    if response.is_error:
        try:
            error_data = response.json()
            if isinstance(error_data, dict):
                error_value = error_data.get("error", error_data)
                if isinstance(error_value, dict):
                    detail = error_value.get("message") or str(error_value)
                else:
                    detail = str(error_value)
            elif isinstance(error_data, list):
                messages = []
                for item in error_data:
                    if isinstance(item, dict):
                        messages.append(str(item.get("message") or item.get("error") or item))
                    else:
                        messages.append(str(item))
                detail = "; ".join(messages)
            else:
                detail = str(error_data)
        except Exception:
            detail = response.text or "Gemini request failed"
        raise HTTPException(status_code=502, detail=f"Gemini API: {detail}")

    data = response.json()
    answer = data.get("output_text")
    if not answer:
        for step in reversed(data.get("steps", [])):
            if step.get("type") == "model_output":
                texts = [
                    part.get("text", "")
                    for part in step.get("content", [])
                    if part.get("type") == "text"
                ]
                answer = "".join(texts).strip()
                if answer:
                    break
    if not answer:
        raise HTTPException(status_code=502, detail="Gemini returned no response")

    return {"reply": answer, "interaction_id": data.get("id")}
