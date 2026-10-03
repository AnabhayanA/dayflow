from datetime import timedelta
from typing import List
from backend.schema import MeetingRequest, MeetingOption
from backend.planner.scheduler import monday, free_windows, mins, clock

def intersect(windows: List[List[tuple[int,int]]]) -> List[tuple[int,int]]:
    if not windows: return []
    current = windows[0]
    for group in windows[1:]:
        nxt = []
        for a,b in current:
            for c,d in group:
                start, end = max(a,c), min(b,d)
                if end > start: nxt.append((start,end))
        current = nxt
    return current

def propose_meetings(req: MeetingRequest) -> List[MeetingOption]:
    week = monday(req.week_start)
    candidates = []
    after = mins(req.preferred_after) if req.preferred_after else None
    before = mins(req.preferred_before) if req.preferred_before else None
    for day in range(7):
        groups = [free_windows(day, req.fixed_blocks, req.availability)]
        for p in req.participants:
            groups.append(free_windows(day, [], p.availability))
        for start, end in intersect(groups):
            if after is not None: start = max(start, after)
            if before is not None: end = min(end, before)
            cursor = start
            while cursor + req.duration <= end:
                actual = week + timedelta(days=day)
                score = 1000 - day * (100 if req.urgency.lower()=="urgent" else 20) - abs(cursor-13*60)//10
                candidates.append((score, actual, day, cursor))
                cursor += 30
    candidates.sort(key=lambda x: (-x[0], x[1], x[3]))
    options = []
    for i, (score, actual, day, start) in enumerate(candidates[:3], 1):
        options.append(MeetingOption(id=i, date=actual.isoformat(), day=day, start=clock(start),
            end=clock(start+req.duration), score=score,
            reason="Earliest strong match" if req.urgency.lower()=="urgent" else "Fits everyone's availability"))
    return options
