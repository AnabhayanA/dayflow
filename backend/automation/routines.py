from datetime import datetime, timedelta


DAY_MAP = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def routine_occurrences(now, days, hour, minute, duration_minutes, weeks=2):
    wanted = {DAY_MAP[d] for d in days if d in DAY_MAP}
    results = []
    date = now.date()
    for offset in range(weeks * 7 + 1):
        current = date + timedelta(days=offset)
        if current.weekday() not in wanted:
            continue
        start = datetime(current.year, current.month, current.day, hour, minute, tzinfo=now.tzinfo)
        if start <= now:
            continue
        results.append((start, start + timedelta(minutes=duration_minutes)))
    return results
