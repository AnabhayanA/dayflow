from datetime import datetime, timedelta, time

from backend.database.connection import get_connection


def upcoming_events(user_id, start, end):
    with get_connection() as connection:
        return connection.execute(
            """SELECT id,title,starts_at,ends_at,flexibility,source
               FROM calendar_events
               WHERE user_id=%s AND starts_at < %s AND ends_at > %s
               ORDER BY starts_at""",
            (user_id, end, start),
        ).fetchall()


def free_windows(user_id, start, end, duration_minutes=60, day_start=8, day_end=22, limit=8):
    events = upcoming_events(user_id, start, end)
    duration = timedelta(minutes=duration_minutes)
    results = []
    cursor_day = start.date()
    while cursor_day <= end.date() and len(results) < limit:
        tz = start.tzinfo
        window_start = datetime.combine(cursor_day, time(day_start, 0), tzinfo=tz)
        window_end = datetime.combine(cursor_day, time(day_end, 0), tzinfo=tz)
        window_start = max(window_start, start)
        window_end = min(window_end, end)
        cursor = window_start
        for event in events:
            ev_start, ev_end = event["starts_at"], event["ends_at"]
            if ev_end <= window_start or ev_start >= window_end:
                continue
            if cursor + duration <= ev_start:
                results.append((cursor, cursor + duration))
                if len(results) >= limit:
                    return results
            if ev_end > cursor:
                cursor = ev_end
        if cursor + duration <= window_end:
            results.append((cursor, cursor + duration))
        cursor_day += timedelta(days=1)
    return results[:limit]
