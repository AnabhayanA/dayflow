import re
from datetime import datetime, timedelta


def _clock(day, hour, minute, meridiem, tz):
    hour = int(hour)
    minute = int(minute or 0)
    if meridiem == "pm" and hour != 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz)


def parse_local_intent(message, now):
    text = message.strip()
    low = text.lower()

    direct = re.search(
        r"(?:schedule|add|book)\s+(.+?)\s+(today|tomorrow)\s+(?:from\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)\s+(?:to|-)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)",
        low,
    )
    if direct:
        day = now.date() + (timedelta(days=1) if direct.group(2) == "tomorrow" else timedelta())
        return {"kind": "create", "title": direct.group(1).strip().title(),
                "start": _clock(day, direct.group(3), direct.group(4), direct.group(5), now.tzinfo),
                "end": _clock(day, direct.group(6), direct.group(7), direct.group(8), now.tzinfo)}

    find = re.search(r"(?:find time for|schedule)\s+(?:the\s+)?(.+?)(?:\s+this week)?$", low)
    if find and ("find time" in low or "this week" in low):
        title = find.group(1).replace(" this week", "").strip().title()
        duration = 60
        hours = re.search(r"(\d+)\s*hours?", low)
        mins = re.search(r"(\d+)\s*minutes?", low)
        if hours:
            duration = int(hours.group(1)) * 60
        elif mins:
            duration = int(mins.group(1))
        return {"kind": "find_time", "title": title, "duration": duration}

    return None
