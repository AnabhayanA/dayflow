from datetime import date, datetime, timedelta
from typing import List, Tuple
from backend.schema import Task, FixedBlock, AvailabilityWindow, ScheduleBlock

PRIORITY = {"high": 3, "medium": 2, "low": 1}
DAY_START, DAY_END, MAX_FOCUS, BREAK = 8 * 60, 21 * 60, 90, 15

def mins(value: str) -> int:
    h, m = map(int, value.split(":"))
    return h * 60 + m

def clock(value: int) -> str:
    h, m = divmod(value, 60)
    suffix = "AM" if h < 12 else "PM"
    return f"{h % 12 or 12}:{m:02d} {suffix}"

def monday(value: str | None) -> date:
    d = datetime.strptime(value, "%Y-%m-%d").date() if value else date.today()
    return d - timedelta(days=d.weekday())

def availability_for(day: int, availability: List[AvailabilityWindow]) -> List[Tuple[int,int]]:
    rows = [(mins(x.start), mins(x.end)) for x in availability if x.day == day]
    return rows or [(DAY_START, DAY_END)]

def busy_for(day: int, blocks: List[FixedBlock]) -> List[Tuple[int,int]]:
    rows = sorted((max(DAY_START, mins(x.start)), min(DAY_END, mins(x.end))) for x in blocks if x.day == day)
    merged: List[List[int]] = []
    for start, end in rows:
        if end <= start: continue
        if not merged or start > merged[-1][1]: merged.append([start, end])
        else: merged[-1][1] = max(merged[-1][1], end)
    return [(a,b) for a,b in merged]

def free_windows(day: int, blocks: List[FixedBlock], availability: List[AvailabilityWindow]) -> List[Tuple[int,int]]:
    busy = busy_for(day, blocks)
    result = []
    for astart, aend in availability_for(day, availability):
        cursor = max(astart, DAY_START)
        limit = min(aend, DAY_END)
        for bstart, bend in busy:
            if bend <= cursor or bstart >= limit: continue
            if bstart > cursor: result.append((cursor, min(bstart, limit)))
            cursor = max(cursor, bend)
        if cursor < limit: result.append((cursor, limit))
    return [(a,b) for a,b in result if b-a >= 15]

def generate_schedule(tasks: List[Task], fixed_blocks: List[FixedBlock], availability: List[AvailabilityWindow], week_start: str | None = None):
    start = monday(week_start)
    ordered = sorted(
        [t for t in tasks if not t.completed],
        key=lambda t: (-PRIORITY.get(t.priority.lower(), 1), t.date or "9999-12-31")
    )
    remaining = {t.id: t.duration for t in ordered}
    schedule = []
    scheduled = 0
    today = date.today()
    for day in range(7):
        actual = start + timedelta(days=day)
        if actual < today: continue
        windows = free_windows(day, fixed_blocks, availability)
        for wstart, wend in windows:
            cursor = wstart
            for task in ordered:
                deadline = datetime.strptime(task.date, "%Y-%m-%d").date() if task.date else None
                if deadline and actual > deadline: continue
                while remaining[task.id] > 0 and cursor < wend:
                    available = wend - cursor
                    length = min(remaining[task.id], MAX_FOCUS, available)
                    if length < 15: break
                    end = cursor + length
                    schedule.append(ScheduleBlock(
                        task_id=task.id, title=task.title, category=task.category,
                        date=actual.isoformat(), day=day, start=clock(cursor), end=clock(end),
                        duration=length, priority=task.priority
                    ))
                    remaining[task.id] -= length
                    scheduled += length
                    cursor = end + (BREAK if end + BREAK <= wend else 0)
                    if remaining[task.id] <= 0: break
    total = sum(t.duration for t in ordered)
    return {"schedule": schedule, "total_minutes": total, "scheduled_minutes": scheduled,
            "unscheduled_minutes": max(total-scheduled, 0)}
