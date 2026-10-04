import hashlib
import logging
from uuid import UUID

import psycopg
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from psycopg.types.json import Jsonb

from backend.workspace_database import get_connection
from backend.schema import FixedBlock, ScheduleBlock, Task

router = APIRouter(prefix="/api", tags=["Workspace"])
logger = logging.getLogger(__name__)


class WorkspaceProfile(BaseModel):
    name: str = "You"
    start: str = "08:00"
    end: str = "21:00"


class SavedMeeting(FixedBlock):
    date: str


class WorkspaceState(BaseModel):
    tasks: list[Task] = Field(max_length=5000)
    blocks: list[FixedBlock] = Field(max_length=5000)
    plan: list[ScheduleBlock] = Field(max_length=10000)
    profile: WorkspaceProfile
    meetings: list[SavedMeeting] = Field(max_length=5000)


def hash_key(key: UUID) -> str:
    return hashlib.sha256(str(key).encode()).hexdigest()


@router.get("/workspace")
def load_workspace(x_dayflow_key: UUID = Header(...)):
    try:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT state, updated_at
                FROM dayflow_workspaces
                WHERE key_hash = %s
                """,
                (hash_key(x_dayflow_key),),
            ).fetchone()
    except psycopg.Error:
        logger.exception("Workspace load failed")
        raise HTTPException(
            status_code=503,
            detail="Database unavailable. Try again shortly.",
        ) from None

    if row is None:
        return {"state": None, "updated_at": None}
    return {"state": row[0], "updated_at": row[1]}


@router.put("/workspace")
def save_workspace(
    state: WorkspaceState,
    x_dayflow_key: UUID = Header(...),
):
    try:
        with get_connection() as connection:
            row = connection.execute(
                """
                INSERT INTO dayflow_workspaces (key_hash, state)
                VALUES (%s, %s)
                ON CONFLICT (key_hash)
                DO UPDATE SET
                    state = EXCLUDED.state,
                    updated_at = NOW()
                RETURNING updated_at
                """,
                (
                    hash_key(x_dayflow_key),
                    Jsonb(state.model_dump(mode="json")),
                ),
            ).fetchone()
    except psycopg.Error:
        logger.exception("Workspace save failed")
        raise HTTPException(
            status_code=503,
            detail="Database unavailable. Your changes were not saved.",
        ) from None
    return {"saved": True, "updated_at": row[0]}

