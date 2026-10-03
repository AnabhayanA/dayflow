from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

app = FastAPI(title="DayFlow API", version="0.5.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "DayFlow API is running"}


@app.get("/api/health")
def health():
    return {
        "status": "online",
        "app": "DayFlow",
        "version": "0.5.0",
        "planner": "online",
        "meetings": "online",
        "assistant": "online",
    }


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
        return ChatResponse(
            message="Tell me what you need help with.",
        )

    if any(word in text for word in ("plan", "schedule", "week", "study")):
        return ChatResponse(
            message=(
                "I can build your week from the tasks and fixed commitments "
                "you've added. Use Plan week and I'll place the flexible work "
                "around everything that cannot move."
            ),
            action="plan",
        )

    if any(word in text for word in ("meet", "meeting", "call")):
        return ChatResponse(
            message=(
                "I can find meeting times that fit your availability. "
                "Open Meetings and choose New meeting to compare three options."
            ),
            action="meeting",
        )

    if any(word in text for word in ("task", "assignment", "homework", "due")):
        return ChatResponse(
            message=(
                "Add the task with its deadline and estimated time. "
                "I'll use those details when I build your week."
            ),
            action="task",
        )

    return ChatResponse(
        message=(
            "I can help you plan your week, add work, or find a meeting time. "
            "Tell me what you're trying to get done."
        ),
    )
