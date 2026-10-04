import os
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlencode

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse

from backend.auth_api import get_current_user, jwt_secret
from backend.database.connection import get_connection

router = APIRouter(prefix="/api/calendars", tags=["Calendars"])

GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO = "https://www.googleapis.com/oauth2/v2/userinfo"
GOOGLE_API = "https://www.googleapis.com/calendar/v3"
GOOGLE_EVENTS = GOOGLE_API + "/calendars/primary/events"
SCOPES = "openid email https://www.googleapis.com/auth/calendar.events"


def setting(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise HTTPException(status_code=503, detail=f"{name} is not configured")
    return value


def oauth_state(user_id) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": str(user_id), "purpose": "google_calendar", "nonce": secrets.token_urlsafe(12),
         "iat": now, "exp": now + timedelta(minutes=10)},
        jwt_secret(), algorithm="HS256"
    )


def read_state(state: str) -> str:
    try:
        payload = jwt.decode(state, jwt_secret(), algorithms=["HS256"])
        if payload.get("purpose") != "google_calendar":
            raise ValueError()
        return payload["sub"]
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or expired calendar connection") from None


@router.get("")
def connections(user=Depends(get_current_user)):
    with get_connection() as connection:
        rows = connection.execute(
            """SELECT id,provider,provider_email,created_at,updated_at
               FROM calendar_connections WHERE user_id=%s ORDER BY created_at""",
            (user["id"],),
        ).fetchall()
    return rows


@router.get("/google/connect")
def google_connect(user=Depends(get_current_user)):
    params = {
        "client_id": setting("GOOGLE_CLIENT_ID"),
        "redirect_uri": setting("GOOGLE_REDIRECT_URI"),
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": oauth_state(user["id"]),
    }
    return {"authorization_url": GOOGLE_AUTH + "?" + urlencode(params)}


@router.get("/google/callback")
def google_callback(code: str, state: str):
    user_id = read_state(state)
    token_response = httpx.post(
        GOOGLE_TOKEN,
        data={
            "code": code,
            "client_id": setting("GOOGLE_CLIENT_ID"),
            "client_secret": setting("GOOGLE_CLIENT_SECRET"),
            "redirect_uri": setting("GOOGLE_REDIRECT_URI"),
            "grant_type": "authorization_code",
        },
        timeout=15,
    )
    if token_response.is_error:
        raise HTTPException(status_code=400, detail="Google calendar authorization failed")
    token = token_response.json()
    access_token = token["access_token"]
    profile_response = httpx.get(
        GOOGLE_USERINFO, headers={"Authorization": f"Bearer {access_token}"}, timeout=15
    )
    profile_response.raise_for_status()
    profile = profile_response.json()
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=token.get("expires_in", 3600))

    with get_connection() as connection:
        existing = connection.execute(
            """SELECT id,refresh_token FROM calendar_connections
               WHERE user_id=%s AND provider='google' AND provider_account_id=%s""",
            (user_id, profile["id"]),
        ).fetchone()
        refresh_token = token.get("refresh_token") or (existing["refresh_token"] if existing else None)
        if existing:
            connection.execute(
                """UPDATE calendar_connections SET provider_email=%s,access_token=%s,
                   refresh_token=%s,token_expires_at=%s,scopes=%s,updated_at=NOW() WHERE id=%s""",
                (profile.get("email"), access_token, refresh_token, expires_at, token.get("scope"), existing["id"]),
            )
        else:
            connection.execute(
                """INSERT INTO calendar_connections
                   (user_id,provider,provider_account_id,provider_email,access_token,refresh_token,token_expires_at,scopes)
                   VALUES(%s,'google',%s,%s,%s,%s,%s,%s)""",
                (user_id, profile["id"], profile.get("email"), access_token, refresh_token, expires_at, token.get("scope")),
            )
        connection.commit()

    # Import the connected calendar immediately so the middle Tempo calendar
    # is populated as soon as OAuth returns.
    try:
        sync_google_for_user(user_id)
    except Exception:
        pass
    return RedirectResponse(os.getenv("FRONTEND_URL", "http://127.0.0.1:5173") + "?calendar=connected")


def valid_google_token(row):
    expires = row["token_expires_at"]
    if expires and expires > datetime.now(timezone.utc) + timedelta(seconds=60):
        return row["access_token"]
    if not row["refresh_token"]:
        raise HTTPException(status_code=401, detail="Reconnect Google Calendar")
    response = httpx.post(
        GOOGLE_TOKEN,
        data={"client_id": setting("GOOGLE_CLIENT_ID"), "client_secret": setting("GOOGLE_CLIENT_SECRET"),
              "refresh_token": row["refresh_token"], "grant_type": "refresh_token"},
        timeout=15,
    )
    if response.is_error:
        raise HTTPException(status_code=401, detail="Reconnect Google Calendar")
    data = response.json()
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=data.get("expires_in", 3600))
    with get_connection() as connection:
        connection.execute(
            "UPDATE calendar_connections SET access_token=%s,token_expires_at=%s,updated_at=NOW() WHERE id=%s",
            (data["access_token"], expires_at, row["id"]),
        )
        connection.commit()
    return data["access_token"]


def latest_google_connection(user_id):
    with get_connection() as connection:
        return connection.execute(
            """SELECT * FROM calendar_connections WHERE user_id=%s AND provider='google'
               ORDER BY updated_at DESC LIMIT 1""", (user_id,)
        ).fetchone()


def create_google_event(user_id, title, start, end):
    row = latest_google_connection(user_id)
    if not row:
        return None
    token = valid_google_token(row)
    response = httpx.post(
        GOOGLE_EVENTS,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"summary": title, "start": {"dateTime": start.isoformat()}, "end": {"dateTime": end.isoformat()}},
        timeout=20,
    )
    if response.is_error:
        raise HTTPException(status_code=502, detail="Google Calendar could not create the event")
    return response.json()


def update_google_event(user_id, external_id, title, start, end):
    if not external_id:
        return
    row = latest_google_connection(user_id)
    if not row:
        return
    token = valid_google_token(row)
    response = httpx.patch(
        f"{GOOGLE_EVENTS}/{external_id}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"summary": title, "start": {"dateTime": start.isoformat()}, "end": {"dateTime": end.isoformat()}},
        timeout=20,
    )
    if response.is_error:
        raise HTTPException(status_code=502, detail="Google Calendar could not update the event")


def delete_google_event(user_id, external_id):
    if not external_id:
        return
    row = latest_google_connection(user_id)
    if not row:
        return
    token = valid_google_token(row)
    response = httpx.delete(
        f"{GOOGLE_EVENTS}/{external_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    if response.status_code not in (200, 204, 404):
        raise HTTPException(status_code=502, detail="Google Calendar could not delete the event")


def sync_google_for_user(user_id):
    row = latest_google_connection(user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Connect Google Calendar first")
    token = valid_google_token(row)
    headers = {"Authorization": f"Bearer {token}"}
    now = datetime.now(timezone.utc)

    # Pull every calendar visible in Google Calendar, not only "primary".
    list_response = httpx.get(GOOGLE_API + "/users/me/calendarList", headers=headers, timeout=20)
    if list_response.is_error:
        raise HTTPException(status_code=502, detail="Google Calendar list sync failed")
    calendars = list_response.json().get("items", [])

    seen = set()
    count = 0
    with get_connection() as connection:
        for calendar in calendars:
            calendar_id = calendar.get("id")
            if not calendar_id or calendar.get("deleted"):
                continue
            page_token = None
            while True:
                params = {
                    "timeMin": (now - timedelta(days=365)).isoformat(),
                    "timeMax": (now + timedelta(days=365)).isoformat(),
                    "singleEvents": "true",
                    "orderBy": "startTime",
                    "maxResults": 2500,
                    "showDeleted": "false",
                }
                if page_token:
                    params["pageToken"] = page_token
                url = GOOGLE_API + "/calendars/" + quote(calendar_id, safe="") + "/events"
                response = httpx.get(url, params=params, headers=headers, timeout=30)
                if response.is_error:
                    continue
                payload = response.json()
                for item in payload.get("items", []):
                    if item.get("status") == "cancelled":
                        continue
                    start_data = item.get("start", {})
                    end_data = item.get("end", {})
                    start = start_data.get("dateTime") or start_data.get("date")
                    end = end_data.get("dateTime") or end_data.get("date")
                    if not start or not end:
                        continue
                    # Calendar ID is part of the external key so identical Google event IDs
                    # from different calendars cannot collide.
                    external_id = calendar_id + "::" + item["id"]
                    seen.add(external_id)
                    connection.execute(
                        """INSERT INTO calendar_events(user_id,title,event_type,starts_at,ends_at,flexibility,source,external_id)
                           VALUES(%s,%s,'Calendar',%s,%s,'fixed','google',%s)
                           ON CONFLICT (user_id,source,external_id) WHERE external_id IS NOT NULL
                           DO UPDATE SET title=EXCLUDED.title,starts_at=EXCLUDED.starts_at,ends_at=EXCLUDED.ends_at""",
                        (user_id, item.get("summary") or "Busy", start, end, external_id),
                    )
                    count += 1
                page_token = payload.get("nextPageToken")
                if not page_token:
                    break

        # Remove stale imported Google rows so Tempo reflects events deleted in Google.
        old_rows = connection.execute(
            "SELECT id,external_id FROM calendar_events WHERE user_id=%s AND source='google'",
            (user_id,),
        ).fetchall()
        for old in old_rows:
            # Keep legacy primary-only IDs until they are naturally replaced; remove only
            # rows using the new calendar-qualified sync format.
            if "::" in (old["external_id"] or "") and old["external_id"] not in seen:
                connection.execute("DELETE FROM calendar_events WHERE id=%s", (old["id"],))
        connection.commit()
    return {"synced": count, "calendars": len(calendars)}


@router.post("/google/sync")
def sync_google(user=Depends(get_current_user)):
    return sync_google_for_user(user["id"])
