from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.models import PlanRequest, PlanResponse, MeetingRequest, MeetingResponse
from backend.planner.scheduler import generate_schedule
from backend.planner.meetings import propose_meetings

app = FastAPI(title="DayFlow API", version="0.4.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:5173","http://localhost:5173","http://127.0.0.1:5500","http://localhost:5500"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/")
def root(): return {"message":"DayFlow API is running"}

@app.get("/api/health")
def health(): return {"status":"online","app":"DayFlow","version":"0.4.0","planner":"online","meetings":"online"}

@app.post("/api/plan", response_model=PlanResponse)
def plan(req: PlanRequest):
    result = generate_schedule(req.tasks, req.fixed_blocks, req.availability, req.week_start)
    if not result["scheduled_minutes"]: msg = "I couldn't find open time for those tasks."
    elif result["unscheduled_minutes"]: msg = "I planned everything that fits before the deadlines. Some work still needs another window."
    else: msg = "Everything fits around your fixed commitments."
    return PlanResponse(message=msg, **result)

@app.post("/api/meetings/propose", response_model=MeetingResponse)
def meetings(req: MeetingRequest):
    return MeetingResponse(options=propose_meetings(req))
