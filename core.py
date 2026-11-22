"""
core.py - pure-Python logic for TaskPilot AI (no Streamlit, no network).

Contains:
  * extract_json()      - robustly pull a JSON object out of raw LLM text
  * resolve_deadline()  - turn "tmrw", "next fri", "by 25th", "in 3 days" into a real date
  * normalise_tasks()   - validate / clean the LLM output into a fixed schema
  * urgency_score()     - one number used to sort tasks (priority + deadline proximity)
  * sort_tasks()        - priority-first sort, then deadline, then urgency
  * offline_extract()   - rule-based fallback so the demo works with no API at all
Everything here is unit-tested in test_core.py.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import date, datetime, timedelta

PRIORITIES = ["High", "Medium", "Low"]
PRIORITY_RANK = {"High": 0, "Medium": 1, "Low": 2}
PRIORITY_WEIGHT = {"High": 60, "Medium": 35, "Low": 10}
CATEGORIES = ["Work", "Study", "Personal", "Health", "Finance", "Errands", "Other"]

WEEKDAYS = {
    "monday": 0, "mon": 0, "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2, "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
    "friday": 4, "fri": 4, "saturday": 5, "sat": 5, "sunday": 6, "sun": 6,
}
MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}


# --------------------------------------------------------------------------- #
# 1. JSON extraction
# --------------------------------------------------------------------------- #
def extract_json(text: str) -> dict:
    """Return the first JSON object found in `text`.

    Handles ```json fences, leading chatter ("Sure! Here is..."), a bare list
    of tasks, and trailing commas. Raises ValueError if nothing parses.
    """
    if not text or not text.strip():
        raise ValueError("Empty response from model")
    cleaned = re.sub(r"```(?:json)?", "", text).strip()

    candidates = [cleaned]
    # outermost {...}
    s, e = cleaned.find("{"), cleaned.rfind("}")
    if s != -1 and e > s:
        candidates.append(cleaned[s:e + 1])
    # outermost [...]
    s, e = cleaned.find("["), cleaned.rfind("]")
    if s != -1 and e > s:
        candidates.append(cleaned[s:e + 1])

    for cand in candidates:
        for attempt in (cand, re.sub(r",\s*([}\]])", r"\1", cand)):
            try:
                data = json.loads(attempt)
            except json.JSONDecodeError:
                continue
            if isinstance(data, list):
                return {"tasks": data}
            if isinstance(data, dict):
                return data
    raise ValueError("Could not find valid JSON in the model response")


# --------------------------------------------------------------------------- #
# 2. Deadline resolution
# --------------------------------------------------------------------------- #
def _next_weekday(today: date, wd: int, force_next_week: bool = False) -> date:
    days = (wd - today.weekday()) % 7
    if days == 0:
        days = 7
    if force_next_week and days < 7 and (today + timedelta(days=days)).isocalendar()[1] == today.isocalendar()[1]:
        days += 7
    return today + timedelta(days=days)


def resolve_deadline(value, today: date | None = None) -> date | None:
    """Convert an ISO date or a relative phrase into a date. None if no deadline."""
    today = today or date.today()
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    v = str(value).strip().lower()
    if v in {"", "none", "null", "n/a", "na", "no deadline", "unknown", "-"}:
        return None

    # ISO yyyy-mm-dd (also accepts yyyy/mm/dd)
    m = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", v)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    # dd/mm or dd-mm(-yyyy)  (Indian format: day first)
    m = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", v)
    if m:
        d, mo = int(m.group(1)), int(m.group(2))
        y = int(m.group(3)) if m.group(3) else today.year
        if y < 100:
            y += 2000
        try:
            out = date(y, mo, d)
            if not m.group(3) and out < today - timedelta(days=60):
                out = date(y + 1, mo, d)
            return out
        except ValueError:
            pass

    if re.search(r"\b(today|tonight|eod|end of day|asap|now|urgent(ly)?)\b", v):
        return today
    if re.search(r"\b(day after tomorrow|day after tmrw)\b", v):
        return today + timedelta(days=2)
    if re.search(r"\b(tomorrow|tmrw|tmr|tomo|tom)\b", v):
        return today + timedelta(days=1)
    m = re.search(r"\bin\s+(\d+|a|one|two|three|four|five)\s+(day|days|week|weeks)\b", v)
    if m:
        words = {"a": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
        n = int(words.get(m.group(1), m.group(1)))
        return today + timedelta(days=n * (7 if "week" in m.group(2) else 1))
    if re.search(r"\b(this weekend|weekend)\b", v):
        return _next_weekday(today, 5) if today.weekday() != 5 else today
    if re.search(r"\b(end of (the )?week|eow|this week)\b", v):
        return today + timedelta(days=(4 - today.weekday()) % 7)
    if re.search(r"\bnext week\b", v):
        return today + timedelta(days=7 - today.weekday())  # next Monday
    if re.search(r"\b(end of (the )?month|eom|this month)\b", v):
        nxt = (today.replace(day=28) + timedelta(days=4))
        return nxt - timedelta(days=nxt.day)
    if re.search(r"\bnext month\b", v):
        nxt = (today.replace(day=28) + timedelta(days=4))
        return nxt.replace(day=1)

    for name, wd in WEEKDAYS.items():
        if re.search(rf"\b(next\s+)?{name}\b", v):
            force = bool(re.search(rf"\bnext\s+{name}\b", v))
            return _next_weekday(today, wd, force_next_week=force)

    # "25 nov", "nov 25", "25th november", "by the 25th"
    m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([a-z]{3,9})\b", v) or None
    if m and m.group(2) in MONTHS:
        d, mo = int(m.group(1)), MONTHS[m.group(2)]
    else:
        m2 = re.search(r"\b([a-z]{3,9})\s+(\d{1,2})(?:st|nd|rd|th)?\b", v)
        if m2 and m2.group(1) in MONTHS:
            d, mo = int(m2.group(2)), MONTHS[m2.group(1)]
        else:
            m3 = re.search(r"\b(?:the\s+)?(\d{1,2})(st|nd|rd|th)\b", v)
            if not m3:
                return None
            d, mo = int(m3.group(1)), today.month
            try:
                out = date(today.year, mo, d)
            except ValueError:
                return None
            if out < today:  # "the 5th" already passed -> next month
                nm = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
                try:
                    out = nm.replace(day=d)
                except ValueError:
                    return None
            return out
    try:
        out = date(today.year, mo, d)
    except ValueError:
        return None
    if out < today - timedelta(days=60):
        out = date(today.year + 1, mo, d)
    return out


# --------------------------------------------------------------------------- #
# 3. Normalisation
# --------------------------------------------------------------------------- #
def _norm_priority(p) -> str:
    p = str(p or "").strip().lower()
    if p in {"high", "h", "urgent", "critical", "p0", "p1", "1", "top"}:
        return "High"
    if p in {"low", "l", "p3", "p4", "3", "4", "minor", "someday"}:
        return "Low"
    return "Medium"


def _norm_category(c) -> str:
    c = str(c or "").strip().title()
    return c if c in CATEGORIES else "Other"


def normalise_tasks(data: dict, today: date | None = None) -> list[dict]:
    """Validate raw model JSON into a clean list of task dicts.

    Output schema per task:
      id, task, priority, deadline (date|None), deadline_text, category,
      est_minutes (int), reason, source, done (bool)
    Duplicate task titles are dropped.
    """
    today = today or date.today()
    raw = data.get("tasks", []) if isinstance(data, dict) else data
    if not isinstance(raw, list):
        raise ValueError("'tasks' must be a list")
    out, seen = [], set()
    for item in raw:
        if isinstance(item, str):
            item = {"task": item}
        if not isinstance(item, dict):
            continue
        title = str(item.get("task") or item.get("title") or item.get("name") or "").strip()
        title = re.sub(r"\s+", " ", title).strip(" -•*.")
        if len(title) < 2:
            continue
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        dl_raw = item.get("deadline") or item.get("due") or item.get("due_date")
        dl = resolve_deadline(dl_raw, today)
        try:
            est = int(float(item.get("est_minutes") or item.get("estimate_minutes") or 30))
        except (TypeError, ValueError):
            est = 30
        out.append({
            "id": uuid.uuid4().hex[:8],
            "task": title[0].upper() + title[1:],
            "priority": _norm_priority(item.get("priority")),
            "deadline": dl,
            "deadline_text": str(item.get("deadline_text") or (dl_raw if dl_raw and not dl else "") or "").strip(),
            "category": _norm_category(item.get("category")),
            "est_minutes": max(5, min(est, 600)),
            "reason": str(item.get("reason") or "").strip(),
            "source": str(item.get("source") or "").strip(),
            "done": bool(item.get("done", False)),
        })
    return out


# --------------------------------------------------------------------------- #
# 4. Ranking
# --------------------------------------------------------------------------- #
def days_left(task: dict, today: date | None = None) -> int | None:
    today = today or date.today()
    return None if task.get("deadline") is None else (task["deadline"] - today).days


def urgency_score(task: dict, today: date | None = None) -> int:
    """0-100. Priority weight + bonus the closer (or more overdue) the deadline."""
    score = PRIORITY_WEIGHT.get(task.get("priority"), 35)
    d = days_left(task, today)
    if d is not None:
        if d < 0:
            score += 40
        elif d == 0:
            score += 35
        elif d <= 2:
            score += 25
        elif d <= 7:
            score += 12
        else:
            score += 4
    return min(score, 100)


def sort_tasks(tasks: list[dict], mode: str = "priority", today: date | None = None) -> list[dict]:
    far = date.max
    if mode == "deadline":
        key = lambda t: (t["deadline"] or far, PRIORITY_RANK[t["priority"]])
    elif mode == "urgency":
        key = lambda t: (-urgency_score(t, today), t["deadline"] or far)
    else:  # priority (default, as required by the problem statement)
        key = lambda t: (PRIORITY_RANK[t["priority"]], t["deadline"] or far, -urgency_score(t, today))
    return sorted(tasks, key=lambda t: (t.get("done", False), key(t)))


def eisenhower_quadrant(task: dict, today: date | None = None) -> str:
    d = days_left(task, today)
    urgent = d is not None and d <= 2
    important = task["priority"] == "High" or (task["priority"] == "Medium" and urgent)
    if urgent and important:
        return "Do first"
    if important:
        return "Schedule"
    if urgent:
        return "Delegate"
    return "Later"


# --------------------------------------------------------------------------- #
# 5. Offline rule-based extractor (fallback when no API / no internet)
# --------------------------------------------------------------------------- #
_HIGH = r"\b(urgent|asap|important|must|critical|exam|deadline|submit|submission|pay|bill|interview|today|tonight|tmrw|tomorrow|overdue|!!+)\b"
_LOW = r"\b(maybe|someday|sometime|if time|when free|optional|later|eventually|could)\b"
_CAT = {
    "Study": r"\b(assignment|exam|study|revise|lab|project|viva|lecture|notes|report|syllabus|homework|quiz)\b",
    "Work": r"\b(meeting|client|email|deck|slides|manager|team|standup|deploy|pr|review|office|internship)\b",
    "Health": r"\b(gym|doctor|dentist|medicine|run|workout|yoga|walk|sleep)\b",
    "Finance": r"\b(pay|bill|rent|emi|bank|fees|tax|recharge|upi|refund)\b",
    "Errands": r"\b(buy|grocer|groceries|pick up|collect|courier|laundry|shop|order|return)\b",
    "Personal": r"\b(call|mom|dad|birthday|friend|family|gift|clean|room)\b",
}
_DEADLINE_HINT = re.compile(
    r"\b(today|tonight|eod|tomorrow|tmrw|tmr|day after tomorrow|next week|this week|end of (?:the )?(?:week|month)|"
    r"this weekend|weekend|(?:with)?in \d+ (?:days?|weeks?)|(?:next |by |on |before )?(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*|"
    r"\d{1,2}(?:st|nd|rd|th)?\s+[a-z]{3,9}|[a-z]{3,9}\s+\d{1,2}(?:st|nd|rd|th)?|\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?|"
    r"\d{4}-\d{2}-\d{2}|(?:the )?\d{1,2}(?:st|nd|rd|th))\b",
    re.I,
)
_FILLER = re.compile(r"^(also|and|then|plus|oh|ok|okay|pls|please|remember to|dont forget to|don't forget to|need to|have to|gotta|i need to|i have to|should|todo:?|to do:?)\s+", re.I)


def offline_extract(notes: str, today: date | None = None) -> dict:
    """Very small heuristic extractor. Same JSON shape as the LLM output."""
    today = today or date.today()
    parts = re.split(r"[\n;•]+|(?<=[.!?])\s+|\s*,\s*(?:and\s+)?(?=(?:also|then|plus|need|have|call|buy|pay|submit|finish|email|book|send|fix|prepare|study|revise|complete|pick|meet|return|clean|go)\b)", notes, flags=re.I)
    tasks = []
    for raw in parts:
        s = raw.strip(" -*\t.")
        if len(s) < 4:
            continue
        s2 = s
        for _ in range(3):
            s2 = _FILLER.sub("", s2).strip()
        lower = s2.lower()
        dl_text, deadline = None, None
        pos = 0
        while (m := _DEADLINE_HINT.search(lower, pos)):  # first hint that really is a date
            cand = resolve_deadline(m.group(0).replace("within", "in"), today)
            if cand:
                dl_text, deadline = m.group(0), cand
                break
            pos = m.start() + 1  # allow overlapping matches ("home 20 dec" -> "20 dec")
        if re.search(_HIGH, lower):
            pr = "High"
        elif re.search(_LOW, lower):
            pr = "Low"
        else:
            pr = "Medium"
        if deadline is not None and (deadline - today).days <= 1 and pr != "Low" and "week" not in (dl_text or ""):
            pr = "High"
        cat = next((c for c, rx in _CAT.items() if re.search(rx, lower)), "Other")
        title = s2
        if dl_text:
            title = re.sub(r"\s*\b(by|before|on|due|until|till|from|this|within)?\s*" + re.escape(dl_text) + r"\b", "", title, flags=re.I)
        title = re.sub(r"\b(urgent(ly)?|asap|!!+|maybe)\b", "", title, flags=re.I)
        title = re.sub(r"\s+", " ", title).strip(" ,.-!")
        if len(title) < 3:
            continue
        tasks.append({
            "task": title, "priority": pr,
            "deadline": deadline.isoformat() if deadline else None,
            "deadline_text": dl_text or "", "category": cat, "est_minutes": 30,
            "reason": "Rule-based: keywords" + (f" + deadline '{dl_text}'" if dl_text else ""),
            "source": s[:120],
        })
    return {"tasks": tasks, "summary": f"Offline mode extracted {len(tasks)} task(s) using rules."}


def fmt_deadline(task: dict, today: date | None = None) -> str:
    d = days_left(task, today)
    if d is None:
        return "No deadline"
    if d < 0:
        return f"Overdue by {-d} day{'s' if d != -1 else ''}"
    if d == 0:
        return "Due today"
    if d == 1:
        return "Due tomorrow"
    if d < 7:
        return f"Due {task['deadline'].strftime('%a, %d %b')} · {d} days"
    return f"Due {task['deadline'].strftime('%d %b %Y')}"
