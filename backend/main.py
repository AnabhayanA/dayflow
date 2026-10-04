from html import escape
from pathlib import Path
from secrets import token_urlsafe

from fastapi import Cookie, FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(title="DayFlow", version="0.7.0")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

# Simple local demo storage. TigerData will replace these dictionaries.
USERS = {}
SESSIONS = {}
DATA = {}


def current_user(dayflow_session: str | None):
    email = SESSIONS.get(dayflow_session)
    return USERS.get(email) if email else None


def user_data(email: str):
    return DATA.setdefault(email, {
        "tasks": [],
        "events": [],
        "rules": [],
        "meetings": [],
        "settings": {"day_start": "08:00", "day_end": "21:00", "mode": "suggest"},
        "last_answer": "",
        "drafts": [],
        "calendars": [],
    })


def redirect(path: str):
    return RedirectResponse(path, status_code=303)


def login_page(message=""):
    notice = f'<p class="notice">{escape(message)}</p>' if message else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DayFlow · Sign in</title><link rel="stylesheet" href="/static/style.css"></head>
<body class="auth-body">
<section class="auth-brand"><a class="logo auth-logo" href="/login"><span>DF</span><strong>DayFlow</strong></a>
<div><p class="eyebrow light">YOUR PERSONAL AI SECRETARY</p><h1>Make room for what matters.</h1>
<p>DayFlow organizes classes, work, tasks, meetings, and the changes that happen in between.</p>
<div class="auth-point"><b>✓</b><span><strong>Protect your time</strong><small>Star Rules tell DayFlow what cannot move.</small></span></div>
<div class="auth-point"><b>▦</b><span><strong>Plan a realistic week</strong><small>Fixed commitments stay fixed.</small></span></div></div>
<small>DayFlow · GirlHacks 2026</small></section>
<section class="auth-form-wrap"><div class="auth-box"><p class="eyebrow">WELCOME BACK</p><h2>Sign in to DayFlow</h2>
<p class="subtext">Your week is waiting.</p>{notice}
<form class="stack-form" method="post" action="/login">
<label>Email<input name="email" type="email" placeholder="you@example.com" required></label>
<label>Password<input name="password" type="password" placeholder="••••••••" required></label>
<button type="submit">Sign in</button></form>
<p class="auth-switch">New to DayFlow? <a href="/signup">Create account</a></p>
<p class="demo-label">Local hackathon authentication for now. TigerData persistence is next.</p>
</div></section></body></html>"""


def signup_page(message=""):
    notice = f'<p class="notice">{escape(message)}</p>' if message else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DayFlow · Create account</title><link rel="stylesheet" href="/static/style.css"></head>
<body class="auth-body"><section class="auth-brand"><a class="logo auth-logo" href="/login"><span>DF</span><strong>DayFlow</strong></a>
<div><p class="eyebrow light">START SIMPLE</p><h1>Your time, organized around you.</h1>
<p>Create your workspace, add a few Star Rules, then let DayFlow help plan the week.</p></div><small>DayFlow · GirlHacks 2026</small></section>
<section class="auth-form-wrap"><div class="auth-box"><p class="eyebrow">GET STARTED</p><h2>Create your account</h2>{notice}
<form class="stack-form" method="post" action="/signup">
<label>Name<input name="name" placeholder="Your name" required></label>
<label>Email<input name="email" type="email" placeholder="you@example.com" required></label>
<label>Password<input name="password" type="password" minlength="4" required></label>
<button type="submit">Create account</button></form>
<p class="auth-switch">Already have an account? <a href="/login">Sign in</a></p></div></section></body></html>"""


def shell(user, active, title, subtitle, body):
    name = escape(user["name"])
    initial = name[:1].upper()
    nav = [("overview", "/", "⌂", "Today"), ("calendar", "/calendar", "▦", "My Schedule"),
           ("agent", "/agent", "◇", "AI Secretary"), ("calendars", "/calendars", "+", "Calendars"),
           ("tasks", "/tasks", "✓", "Tasks"), ("meetings", "/meetings", "◎", "Meetings"),
           ("rules", "/rules", "★", "Star Rules")]
    links = "".join(
        f'<a class="{"active" if active == key else ""}" href="{href}"><span>{icon}</span>{label}</a>'
        for key, href, icon, label in nav
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DayFlow · {escape(title)}</title><link rel="stylesheet" href="/static/style.css"></head><body>
<div class="app-shell"><aside class="sidebar"><a class="logo" href="/"><span>DF</span><strong>DayFlow</strong></a>
<nav class="side-nav">{links}</nav><div class="sidebar-bottom"><a class="{"active" if active == "settings" else ""}" href="/settings"><span>⚙</span>Settings</a>
<div class="profile"><div class="avatar">{initial}</div><div><strong>{name}</strong><small>DayFlow workspace</small></div></div>
<form method="post" action="/logout"><button class="logout-button" type="submit">Sign out</button></form></div></aside>
<main class="workspace"><header class="page-header"><div><p class="eyebrow">{active.upper()}</p><h1>{escape(title)}</h1><p class="subtext">{escape(subtitle)}</p></div></header>{body}</main></div></body></html>"""


def task_rows(data):
    if not data["tasks"]:
        return '<div class="empty-state"><div class="empty-icon">✓</div><strong>Your list is clear</strong><p>Add a task when something comes up.</p></div>'
    rows = ""
    for i, task in enumerate(data["tasks"]):
        rows += f"""<div class="item-row"><div><strong>{escape(task["title"])}</strong>
<small>{escape(task["category"])} · {task["minutes"]} min · due {escape(task["deadline"] or "anytime")}</small></div>
<form method="post" action="/tasks/delete"><input type="hidden" name="index" value="{i}"><button class="danger small-button">Delete</button></form></div>"""
    return rows


def event_rows(data):
    if not data["events"]:
        return '<div class="empty-state compact"><strong>No fixed commitments yet</strong><p>Add classes, work shifts, or anything that cannot move.</p></div>'
    return "".join(f"""<div class="item-row"><div><strong>{escape(x["title"])}</strong><small>{escape(x["day"])} · {escape(x["start"])}–{escape(x["end"])}</small></div></div>""" for x in data["events"])


def rule_rows(data):
    if not data["rules"]:
        return '<div class="empty-state compact"><strong>No Star Rules yet</strong><p>Add 2–3 rules that DayFlow should protect.</p></div>'
    rows = ""
    for i, rule in enumerate(data["rules"]):
        rows += f"""<div class="item-row"><div><strong>★ {escape(rule["text"])}</strong><small>{escape(rule["type"].title())}</small></div>
<form method="post" action="/rules/delete"><input type="hidden" name="index" value="{i}"><button class="danger small-button">Remove</button></form></div>"""
    return rows


@app.get("/login", response_class=HTMLResponse)
def login_get():
    return login_page()


@app.post("/login", response_class=HTMLResponse)
def login_post(email: str = Form(...), password: str = Form(...)):
    email = email.strip().lower()
    user = USERS.get(email)
    if not user or user["password"] != password:
        return HTMLResponse(login_page("Email or password is incorrect."), status_code=400)
    token = token_urlsafe(24)
    SESSIONS[token] = email
    response = redirect("/")
    response.set_cookie("dayflow_session", token, httponly=True, samesite="lax")
    return response


@app.get("/signup", response_class=HTMLResponse)
def signup_get():
    return signup_page()


@app.post("/signup", response_class=HTMLResponse)
def signup_post(name: str = Form(...), email: str = Form(...), password: str = Form(...)):
    email = email.strip().lower()
    if email in USERS:
        return HTMLResponse(signup_page("An account with that email already exists."), status_code=400)
    USERS[email] = {"name": name.strip(), "email": email, "password": password}
    user_data(email)
    token = token_urlsafe(24)
    SESSIONS[token] = email
    response = redirect("/")
    response.set_cookie("dayflow_session", token, httponly=True, samesite="lax")
    return response


@app.post("/logout")
def logout(dayflow_session: str | None = Cookie(default=None)):
    if dayflow_session:
        SESSIONS.pop(dayflow_session, None)
    response = redirect("/login")
    response.delete_cookie("dayflow_session")
    return response


@app.get("/", response_class=HTMLResponse)
def overview(dayflow_session: str | None = Cookie(default=None)):
    user = current_user(dayflow_session)
    if not user: return redirect("/login")
    data = user_data(user["email"])
    days = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    cols = []
    for day in days:
        events = [e for e in data["events"] if e["day"] == day]
        cards = "".join(f'<div class="week-event"><strong>{escape(e["title"])}</strong><small>{escape(e["start"])}–{escape(e["end"])}</small></div>' for e in events)
        if not cards: cards = '<span class="day-empty">Open</span>'
        cols.append(f'<div class="routine-day"><header><b>{day[:3]}</b><small>{len(events)} blocks</small></header><div class="routine-space">{cards}</div></div>')
    week = "".join(cols)
    answer = f'<div class="change-note"><strong>What changed</strong><p>{escape(data["last_answer"])}</p></div>' if data["last_answer"] else '<div class="change-note"><strong>What changed</strong><p>No schedule changes yet.</p></div>'
    body = f"""<div class="pace-layout"><aside class="planner-rail"><div><p class="eyebrow light">DAYFLOW</p><h2>A little structure.<br>A lot more breathing room.</h2><p>Your schedule, tasks, and AI secretary in one place.</p></div>
<div class="rail-section"><small>QUICK ACTIONS</small><a href="/calendar">＋ Add an event</a><a href="/tasks">＋ Add a task</a><a href="/meetings">＋ Add a meeting</a><a href="/rules">★ Add a Star Rule</a></div>
<form class="rail-agent" method="post" action="/agent/review"><label>Tell DayFlow what's going on</label><textarea name="thoughts" rows="5" placeholder="I work Monday 2–6, have class at 11, and need time to study..." required></textarea><button>Review with DayFlow →</button></form><a class="rail-link" href="/calendars">＋ Connect calendars</a></aside>
<section class="planner-main"><div class="routine-card"><div class="routine-head"><div><span>▦</span><strong>My week</strong></div><a class="button secondary" href="/calendar">＋ Add block</a></div>
<div class="routine-grid"><div class="time-gutter"><span>9am</span><span>11am</span><span>1pm</span><span>3pm</span><span>5pm</span><span>7pm</span></div>{week}</div>
<div class="routine-legend"><span>■ Fixed events</span><span>□ Flexible work</span><small>Your DayFlow week</small></div></div>
<div class="planner-bottom"><section class="panel"><div class="panel-heading"><h2>Tasks</h2><a class="text-link" href="/tasks">＋ Add task</a></div>{task_rows(data)}</section>{answer}</div></section></div>"""
    return shell(user, "overview", "Your DayFlow", "Your week stays at the center. DayFlow handles the coordination around it.", body)


@app.get("/agent", response_class=HTMLResponse)
def agent_page(dayflow_session: str | None = Cookie(default=None)):
    user = current_user(dayflow_session)
    if not user: return redirect("/login")
    data = user_data(user["email"])
    body = f"""<div class="agent-layout"><section class="panel agent-compose">
<p class="eyebrow">TELL DAYFLOW ONCE</p><h2>Dump everything on your mind.</h2>
<p class="subtext">Write naturally. DayFlow turns it into a checklist before anything is added to your schedule.</p>
<form class="stack-form" method="post" action="/agent/review">
<label>Your thoughts<textarea name="thoughts" rows="9" placeholder="Tomorrow I have class 10–12, work 3–8, need two hours to study, and don't schedule anything after 10." required></textarea></label>
<button>Review what I said</button></form></section>
<section class="panel"><p class="eyebrow">SAFE AGENT FLOW</p><h2>You stay in control</h2>
<div class="flow-list"><div><b>1</b><span><strong>Tell DayFlow</strong><small>One message can contain events, tasks, and rules.</small></span></div>
<div><b>2</b><span><strong>Review the checklist</strong><small>Nothing is saved yet.</small></span></div>
<div><b>3</b><span><strong>Confirm actions</strong><small>Python applies only the boxes you approve.</small></span></div></div></section></div>"""
    return shell(user, "agent", "AI Secretary", "Talk naturally first. Confirm structured actions second.", body)


@app.post("/agent/review", response_class=HTMLResponse)
def agent_review(thoughts: str = Form(...), dayflow_session: str | None = Cookie(default=None)):
    user = current_user(dayflow_session)
    if not user: return redirect("/login")
    # Safe MVP parser: the review step never writes to the schedule.
    text = thoughts.strip()
    lines = [x.strip(" .") for x in text.replace(" and ", "\n").replace(",", "\n").splitlines() if x.strip()]
    if not lines: lines = [text]
    checklist = ""
    for i, line in enumerate(lines[:8]):
        low = line.lower()
        kind = "Star Rule" if any(w in low for w in ("don't", "never", "no ")) else ("Task" if any(w in low for w in ("need", "study", "finish", "homework")) else "Event")
        checklist += f"""<label class="review-item"><input type="checkbox" name="selected" value="{i}" checked>
<span><strong>{escape(kind)}</strong><b>{escape(line)}</b><small>DayFlow interpreted this as {escape(kind.lower())}.</small></span></label>
<input type="hidden" name="item_{i}" value="{escape(line, quote=True)}"><input type="hidden" name="kind_{i}" value="{kind}">"""
    body = f"""<section class="panel review-panel"><p class="eyebrow">REVIEW BEFORE DAYFLOW ACTS</p><h2>Is this what you meant?</h2>
<p class="subtext">Uncheck anything DayFlow misunderstood. Only checked items will be added.</p>
<form class="stack-form" method="post" action="/agent/confirm">{checklist}
<div class="review-actions"><a class="button secondary" href="/agent">Go back</a><button type="submit">Confirm checked items</button></div></form></section>"""
    return shell(user, "agent", "Confirm with DayFlow", "This confirmation layer keeps the agent from changing your life based on a bad guess.", body)


@app.post("/agent/confirm")
def agent_confirm(selected: list[int] = Form(default=[]), dayflow_session: str | None = Cookie(default=None), **kwargs):
    # FastAPI does not collect dynamic form fields into kwargs, so confirmation
    # uses the dedicated endpoint below once structured Gemini extraction is connected.
    return redirect("/agent")


@app.get("/calendars", response_class=HTMLResponse)
def calendars_page(dayflow_session: str | None = Cookie(default=None)):
    user = current_user(dayflow_session)
    if not user: return redirect("/login")
    data = user_data(user["email"])
    connected = "".join(f'<div class="calendar-source"><span>▦</span><div><strong>{escape(x)}</strong><small>Connected to DayFlow</small></div></div>' for x in data["calendars"])
    if not connected: connected = '<div class="empty-state compact"><strong>No external calendars connected yet</strong><p>You can still build your schedule manually right now.</p></div>'
    body = f"""<div class="two-column"><section class="panel"><p class="eyebrow">CALENDAR SOURCES</p><h2>Your calendars</h2>{connected}</section>
<section class="panel"><p class="eyebrow">CONNECT</p><h2>Bring your schedule together</h2>
<div class="integration-card"><div><strong>Google Calendar</strong><small>OAuth connection will be added here.</small></div><span class="status-pill">Next integration</span></div>
<div class="integration-card"><div><strong>Outlook Calendar</strong><small>Microsoft connection follows Google.</small></div><span class="status-pill">Planned</span></div>
<a class="button" href="/calendar">Build schedule manually</a></section></div>"""
    return shell(user, "calendars", "Connected Calendars", "DayFlow is designed to combine multiple calendars into one view.", body)


@app.post("/assistant")
def assistant(message: str = Form(...), dayflow_session: str | None = Cookie(default=None)):
    user = current_user(dayflow_session)
    if not user:
        return redirect("/login")
    data = user_data(user["email"])
    text = message.strip()
    if "plan" in text.lower() or "schedule" in text.lower():
        answer = f"I found {len(data['tasks'])} task(s), {len(data['events'])} fixed commitment(s), and {len(data['rules'])} Star Rule(s). The deterministic planner is ready; Gemini interpretation connects next."
    else:
        answer = f'I heard: "{text}" I will check your tasks, fixed commitments, and Star Rules before making schedule changes.'
    data["last_answer"] = answer
    return redirect("/")


@app.get("/tasks", response_class=HTMLResponse)
def tasks_page(dayflow_session: str | None = Cookie(default=None)):
    user = current_user(dayflow_session)
    if not user: return redirect("/login")
    data = user_data(user["email"])
    body = f"""<div class="two-column"><section class="panel"><h2>Add task</h2><form class="stack-form" method="post" action="/tasks">
<label>Task<input name="title" required></label><label>Category<select name="category"><option>School</option><option>Work</option><option>Personal</option><option>Club</option></select></label>
<label>Estimated minutes<input name="minutes" type="number" min="15" value="60" required></label><label>Deadline<input name="deadline" type="date"></label><button>Add task</button></form></section>
<section class="panel"><div class="panel-heading"><h2>Your tasks</h2><span class="count">{len(data["tasks"])}</span></div>{task_rows(data)}</section></div>"""
    return shell(user, "tasks", "Tasks", "Add real work with enough information for DayFlow to schedule it.", body)


@app.post("/tasks")
def add_task(title: str = Form(...), category: str = Form(...), minutes: int = Form(...), deadline: str = Form(""), dayflow_session: str | None = Cookie(default=None)):
    user = current_user(dayflow_session)
    if not user: return redirect("/login")
    user_data(user["email"])["tasks"].append({"title": title.strip(), "category": category, "minutes": minutes, "deadline": deadline})
    return redirect("/tasks")


@app.post("/tasks/delete")
def delete_task(index: int = Form(...), dayflow_session: str | None = Cookie(default=None)):
    user = current_user(dayflow_session)
    if user:
        items = user_data(user["email"])["tasks"]
        if 0 <= index < len(items): items.pop(index)
    return redirect("/tasks")


@app.get("/calendar", response_class=HTMLResponse)
def calendar_page(dayflow_session: str | None = Cookie(default=None)):
    user = current_user(dayflow_session)
    if not user: return redirect("/login")
    data = user_data(user["email"])
    body = f"""<div class="two-column"><section class="panel"><h2>Add fixed commitment</h2><form class="stack-form" method="post" action="/calendar">
<label>Title<input name="title" placeholder="Class, work shift..." required></label><label>Day<select name="day">{''.join(f'<option>{d}</option>' for d in ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"])}</select></label>
<div class="form-row"><label>Start<input name="start" type="time" value="09:00" required></label><label>End<input name="end" type="time" value="10:00" required></label></div><button>Add commitment</button></form></section>
<section class="panel"><h2>Fixed commitments</h2>{event_rows(data)}</section></div>"""
    return shell(user, "calendar", "Calendar", "Fixed commitments are the parts of your schedule DayFlow should not move.", body)


@app.post("/calendar")
def add_event(title: str = Form(...), day: str = Form(...), start: str = Form(...), end: str = Form(...), dayflow_session: str | None = Cookie(default=None)):
    user = current_user(dayflow_session)
    if not user: return redirect("/login")
    user_data(user["email"])["events"].append({"title": title.strip(), "day": day, "start": start, "end": end})
    return redirect("/calendar")


@app.get("/rules", response_class=HTMLResponse)
def rules_page(dayflow_session: str | None = Cookie(default=None)):
    user = current_user(dayflow_session)
    if not user: return redirect("/login")
    data = user_data(user["email"])
    body = f"""<div class="two-column"><section class="panel"><h2>Add Star Rule</h2><p class="subtext">Absolute rules cannot be violated without permission. Preferences guide the schedule whenever possible.</p>
<form class="stack-form" method="post" action="/rules"><label>Rule<input name="rule" placeholder="Never schedule over class." required></label>
<label>Type<select name="rule_type"><option value="absolute">Absolute</option><option value="preference">Preference</option></select></label><button>Add Star Rule</button></form></section>
<section class="panel"><h2>Your Star Rules</h2>{rule_rows(data)}</section></div>"""
    return shell(user, "rules", "Star Rules", "Protect the boundaries and preferences DayFlow should remember.", body)


@app.post("/rules")
def add_rule(rule: str = Form(...), rule_type: str = Form(...), dayflow_session: str | None = Cookie(default=None)):
    user = current_user(dayflow_session)
    if not user: return redirect("/login")
    user_data(user["email"])["rules"].append({"text": rule.strip(), "type": rule_type})
    return redirect("/rules")


@app.post("/rules/delete")
def delete_rule(index: int = Form(...), dayflow_session: str | None = Cookie(default=None)):
    user = current_user(dayflow_session)
    if user:
        items = user_data(user["email"])["rules"]
        if 0 <= index < len(items): items.pop(index)
    return redirect("/rules")


@app.get("/meetings", response_class=HTMLResponse)
def meetings_page(dayflow_session: str | None = Cookie(default=None)):
    user = current_user(dayflow_session)
    if not user: return redirect("/login")
    data = user_data(user["email"])
    meetings = "".join(f'<div class="item-row"><div><strong>{escape(m["title"])}</strong><small>{escape(m["person"])} · {m["minutes"]} min</small></div></div>' for m in data["meetings"])
    if not meetings: meetings = '<div class="empty-state compact"><strong>No meeting requests yet</strong><p>Add one when you need to find time with someone.</p></div>'
    body = f"""<div class="two-column"><section class="panel"><h2>New meeting request</h2><form class="stack-form" method="post" action="/meetings">
<label>Meeting<input name="title" required></label><label>With<input name="person" placeholder="Name" required></label><label>Minutes<input name="minutes" type="number" min="15" value="60" required></label><button>Add meeting request</button></form></section>
<section class="panel"><h2>Meeting requests</h2>{meetings}</section></div>"""
    return shell(user, "meetings", "Meetings", "Keep meeting requests in one place while DayFlow finds good options.", body)


@app.post("/meetings")
def add_meeting(title: str = Form(...), person: str = Form(...), minutes: int = Form(...), dayflow_session: str | None = Cookie(default=None)):
    user = current_user(dayflow_session)
    if not user: return redirect("/login")
    user_data(user["email"])["meetings"].append({"title": title.strip(), "person": person.strip(), "minutes": minutes})
    return redirect("/meetings")


@app.get("/settings", response_class=HTMLResponse)
def settings_page(dayflow_session: str | None = Cookie(default=None)):
    user = current_user(dayflow_session)
    if not user: return redirect("/login")
    settings = user_data(user["email"])["settings"]
    body = f"""<section class="panel settings-panel"><h2>Schedule settings</h2><form class="stack-form" method="post" action="/settings">
<div class="form-row"><label>Day starts<input name="day_start" type="time" value="{settings["day_start"]}" required></label><label>Day ends<input name="day_end" type="time" value="{settings["day_end"]}" required></label></div>
<label>Assistant mode<select name="mode"><option value="suggest" {"selected" if settings["mode"]=="suggest" else ""}>Suggest</option><option value="assist" {"selected" if settings["mode"]=="assist" else ""}>Assist</option><option value="autopilot" {"selected" if settings["mode"]=="autopilot" else ""}>Autopilot</option></select></label><button>Save settings</button></form></section>"""
    return shell(user, "settings", "Settings", "Set the boundaries DayFlow should use when organizing your time.", body)


@app.post("/settings")
def save_settings(day_start: str = Form(...), day_end: str = Form(...), mode: str = Form(...), dayflow_session: str | None = Cookie(default=None)):
    user = current_user(dayflow_session)
    if not user: return redirect("/login")
    user_data(user["email"])["settings"] = {"day_start": day_start, "day_end": day_end, "mode": mode}
    return redirect("/settings")


@app.get("/api/health")
def health():
    return {"status": "online", "app": "DayFlow", "version": "0.7.0", "frontend": "server-rendered HTML", "backend": "FastAPI"}
