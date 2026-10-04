import os
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from pwdlib import PasswordHash

from backend.database.connection import get_connection

router = APIRouter(prefix="/auth", tags=["Auth"])
bearer = HTTPBearer()
password_hash = PasswordHash.recommended()


class SignupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    mode: str = "other"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


def jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise RuntimeError("JWT_SECRET is not configured")
    return secret


def create_token(user_id: UUID) -> str:
    minutes = int(os.getenv("ACCESS_TOKEN_MINUTES", "10080"))
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=minutes)},
        jwt_secret(),
        algorithm="HS256",
    )


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    try:
        payload = jwt.decode(credentials.credentials, jwt_secret(), algorithms=["HS256"])
        user_id = UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired session") from None

    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, email, name, mode FROM users WHERE id = %s",
            (user_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="User no longer exists")
    return row


@router.post("/signup", status_code=201)
def signup(body: SignupRequest):
    mode = body.mode if body.mode in {"student", "office", "other"} else "other"
    try:
        with get_connection() as connection:
            row = connection.execute(
                """
                INSERT INTO users (email, password_hash, name, mode)
                VALUES (%s, %s, %s, %s)
                RETURNING id, email, name, mode
                """,
                (body.email.lower(), password_hash.hash(body.password), body.name.strip(), mode),
            ).fetchone()
            connection.execute(
                "INSERT INTO profiles (user_id) VALUES (%s) ON CONFLICT DO NOTHING",
                (row["id"],),
            )
            connection.commit()
    except Exception as exc:
        if "unique" in str(exc).lower():
            raise HTTPException(status_code=409, detail="Email already registered") from None
        raise
    return {"token": create_token(row["id"]), "user": row}


@router.post("/login")
def login(body: LoginRequest):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, email, name, mode, password_hash FROM users WHERE email = %s",
            (body.email.lower(),),
        ).fetchone()
    if not row or not password_hash.verify(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    user = {k: row[k] for k in ("id", "email", "name", "mode")}
    return {"token": create_token(row["id"]), "user": user}


@router.get("/me")
def me(user=Depends(get_current_user)):
    return user
