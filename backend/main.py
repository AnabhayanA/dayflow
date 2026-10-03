from pathlib import Path

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from backend.planner.meetings import propose_meetings
from backend.planner.scheduler import generate_schedule
from backend.schema import (
    ChatRequest,
    ChatResponse,
    MeetingRequest,
    MeetingResponse,
    PlanRequest,
    PlanResponse,
)

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(title="DayFlow API", version="0.6.0")

app.mount(
    "/static",
    StaticFiles(directory=FRONTEND_DIR),
    name="static",
)


def read_frontend_page() -> str:
    return (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/", response_class=HTMLResponse)
def home():
    return read_frontend_page()


@app.get("/api/health")
def health():
    return {
        "status": "online",
        "app": "DayFlow",
        "version": "0.6.0",
        "planner": "online",
        "meetings": "online",
        "assistant": "online",
    }


@app.post("/assistant", response_class=HTMLResponse)
def assistant_form(message: str = Form(...)):
    safe_message = message.strip()

    return f"""
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>DayFlow</title>
      <link rel="stylesheet" href="/static/style.css">
    </head>
    <body>
      <main class="page">
        <section class="card">
          <p class="eyebrow">DAYFLOW ASSISTANT</p>
          <h1>Got it.</h1>
          <p>You told DayFlow: {safe_message}</p>
          <p>The Gemini scheduling assistant will connect here next.</p>
          <a href="/">Back to DayFlow</a>
        </section>
      </main>
    </body>
    </html>
    """


@app.post("/rules", response_class=HTMLResponse)
def add_rule_form(
    rule: str = Form(...),
    rule_type: str = Form(...),
):
    return f"""
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>DayFlow</title>
      <link rel="stylesheet" href="/static/style.css">
    </head>
    <body>
      <main class="page">
        <section class="card">
          <p class="eyebrow">STAR RULE ADDED</p>
          <h1>{rule}</h1>
          <p>Type: {rule_type.title()}</p>
          <p>Database persistence will be connected to this form next.</p>
          <a href="/">Back to DayFlow</a>
        </section>
      </main>
    </body>
    </html>
    """


@app.post("/api/plan", response_model=PlanResponse)
def create_plan(request: PlanRequest):
    result = generate_schedule(
        request.tasks,
        request.fixed_blocks,
        request.availability,
        request.week_start,
    )

    if not result["scheduled_minutes"]:
        message = "I couldn't find open time for those tasks."
    elif result["unscheduled_minutes"]:
        message = (
            "I planned everything that fits before the deadlines. "
            "Some work still needs another window."
        )
    else:
        message = "Everything fits around your fixed commitments."

    return PlanResponse(message=message, **result)


@app.post("/api/meetings/propose", response_model=MeetingResponse)
def propose_meeting_times(request: MeetingRequest):
    return MeetingResponse(options=propose_meetings(request))


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    text = request.message.strip().lower()

    if not text:
        return ChatResponse(message="Tell me what you need help with.")

    if any(word in text for word in ("plan", "schedule", "week", "study")):
        return ChatResponse(
            message=(
                "I can build your week from your tasks and fixed commitments."
            ),
            action="plan",
        )

    if any(word in text for word in ("meet", "meeting", "call")):
        return ChatResponse(
            message="I can find meeting times that fit your availability.",
            action="meeting",
        )

    if any(word in text for word in ("task", "assignment", "homework", "due")):
        return ChatResponse(
            message="Tell me the deadline and how long the task should take.",
            action="task",
        )

    return ChatResponse(
        message=(
            "I can help plan your week, protect Star Rules, "
            "or respond when your schedule changes."
        )
    )
