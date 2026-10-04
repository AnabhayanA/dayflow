import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.auth_api import get_current_user
from backend.database.connection import get_connection

router = APIRouter(prefix="/api/ai", tags=["Tempo AI"])

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"

class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    timezone: str = Field(default="America/New_York", max_length=100)
    conversation: list[dict] = Field(default_factory=list)

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
    now_utc = datetime.now(timezone.utc)
    try:
        user_tz = ZoneInfo(body.timezone)
    except Exception:
        user_tz = timezone.utc
    local_now = now_utc.astimezone(user_tz)
    now = now_utc.isoformat()
    local_now_text = local_now.strftime("%A, %B %d, %Y at %I:%M %p")
    prompt = f"""You are Tempo, an AI personal secretary and scheduling assistant.
You are speaking to {user['name']} whose mode is {user['mode']}.
Current UTC time (internal only): {now}
User local time: {local_now_text}
User IANA timezone: {body.timezone}

Rules:
- Your job is to PLAN and offer decisions, not write an essay.\n- Default visible answer: maximum 2 short sentences plus tap choices. Do not greet the user unless they greeted you.\n- Do not restate the user's request or summarize their whole week.\n- Return plain text only; do not use Markdown formatting.\n- Be concise, practical, warm, and decisive. Do not sound like a generic chatbot.
- Use ONLY the schedule/task context below for claims about this user's calendar. Never invent events, deadlines, free time, or commitments.
- Treat fixed/calendar events as protected. Never suggest moving classes, meetings, work shifts, or other fixed commitments unless the user explicitly asks.
- Protect high-priority tasks before medium/low-priority tasks.
- Interpret relative words like today, tonight, tomorrow, morning, and evening in the user's IANA timezone, not UTC.
- Event/task timestamps may be stored with timezone offsets. Convert them to the user's local timezone before presenting times.
- NEVER show UTC to the user unless they explicitly ask for UTC. Convert and present times in the user's local timezone using 12-hour AM/PM format.\n- Never print 24-hour clock times unless the user explicitly requests that format.
- When asked to find time, reason around the listed event start/end times and give concrete candidate windows.\n- If no calendar events are supplied, say that you do not have calendar events to work around yet; never claim the calendar is clear, empty, flexible, or open.\n- An unscheduled task is not a calendar commitment.\n- Prefer useful tap choices over broad preference questions.
- Do not claim that you created, moved, or deleted anything. This chat endpoint currently advises and proposes; actual changes require explicit user approval through Tempo.
- For destructive or significant schedule changes, clearly ask for confirmation first.
- If the user asks for something unrelated to scheduling/productivity, you may answer briefly but steer back to their goal when useful.
- Think through the schedule carefully, but keep the visible response extremely short: normally 1 to 2 sentences.
- Prefer making a concrete recommendation over explaining your reasoning at length.
- Use the recent conversation to understand follow-ups like "yes", "second one", "tomorrow instead", and "other times".
- End with 2 to 4 short tap choices whenever a useful next decision exists.
- Put each choice on its own final line using exactly: [ACTION] choice text
- Never put [ACTION] inside the main prose.\n- When the user has given enough information to create a calendar block, include one final machine-readable line: [CREATE_EVENT] title | ISO-8601 start with timezone offset | ISO-8601 end with timezone offset | event type\n- Only emit CREATE_EVENT when start and end are concrete and do not overlap a supplied fixed event.\n- If details are missing, use ACTION choices instead of inventing them.

RECENT CONVERSATION:
{chr(10).join(str(m.get("role","user")) + ": " + str(m.get("text","")) for m in body.conversation[-8:]) or "- First message."}

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
            timeout=httpx.Timeout(75.0, connect=15.0),
        )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Gemini took too long to respond. Try again.") from None
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Gemini connection failed: {exc.__class__.__name__}") from None

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

    suggestions = []
    actions = []
    reply_lines = []
    for line in answer.splitlines():
        stripped = line.strip()
        if stripped.startswith("[ACTION]"):
            value = stripped[8:].strip()
            if value:
                suggestions.append(value)
        elif stripped.startswith("[CREATE_EVENT]"):
            parts = [p.strip() for p in stripped[14:].strip().split("|")]
            if len(parts) >= 3:
                actions.append({
                    "type": "create_event",
                    "label": "Add to calendar",
                    "title": parts[0],
                    "start": parts[1],
                    "end": parts[2],
                    "event_type": parts[3] if len(parts) > 3 else "Personal",
                })
        else:
            reply_lines.append(line)
    reply = "\n".join(reply_lines).strip() or answer
    return {"reply": reply, "suggestions": suggestions[:4], "actions": actions[:1], "interaction_id": data.get("id")}
