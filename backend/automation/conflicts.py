from backend.database.connection import get_connection


def find_conflict(user_id, start, end, exclude_id=None):
    sql = """SELECT id,title,starts_at,ends_at,source FROM calendar_events
             WHERE user_id=%s AND flexibility='fixed' AND starts_at < %s AND ends_at > %s"""
    args = [user_id, end, start]
    if exclude_id:
        sql += " AND id <> %s"
        args.append(exclude_id)
    with get_connection() as connection:
        return connection.execute(sql + " ORDER BY starts_at LIMIT 1", args).fetchone()
