# DayFlow

AI-assisted work, school, life, and meeting planner.

## Stack
- React + Vite frontend
- FastAPI + Python scheduling backend
- LocalStorage persistence for hackathon MVP

## Run
Backend:
```bash
python -m venv venv
source venv/Scripts/activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173.

## Phase 1
Tasks, fixed commitments, availability, deadline-aware multi-day planning, focus blocks that avoid conflicts.

## Phase 2
Profile availability, meeting requests, urgent/normal scheduling, three proposed times, confirmation into the calendar, starred tasks and persistent meeting data.

Gemini and voice integrations are intentionally isolated for the next sponsor-integration phase.
