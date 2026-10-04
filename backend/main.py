from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.auth_api import router as auth_router
from backend.calendar_api import router as calendar_router
from backend.planner_api import router as planner_router
from backend.sharing_api import router as sharing_router
from backend.workspace_api import router as workspace_router

app = FastAPI(title="DayFlow API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(planner_router)
app.include_router(calendar_router)
app.include_router(sharing_router)

# Preserve the TigerData workspace API added by the team.
# The React app will move from workspace snapshots to the user-scoped APIs above.
app.include_router(workspace_router)


@app.get("/")
def root():
    return {"message": "DayFlow API is running", "version": "1.0.0"}


@app.get("/api/health")
def health():
    return {
        "status": "online",
        "app": "DayFlow",
        "backend": "FastAPI",
        "database": "TigerData/Postgres",
    }
