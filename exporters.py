"""exporters.py - turn the task list into CSV, JSON, Markdown and an .ics calendar file."""
from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime, timedelta

from core import fmt_deadline


def to_rows(tasks):
    return [{
        "Done": "Yes" if t["done"] else "No", "Task": t["task"], "Priority": t["priority"],
        "Deadline": t["deadline"].isoformat() if t["deadline"] else "",
        "Category": t["category"], "Est. minutes": t["est_minutes"], "Reason": t["reason"],
    } for t in tasks]


def to_csv(tasks) -> str:
    buf = io.StringIO()
    rows = to_rows(tasks)
    w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()) if rows else ["Task"])
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def to_json(tasks) -> str:
    return json.dumps([{**t, "deadline": t["deadline"].isoformat() if t["deadline"] else None}
                       for t in tasks], indent=2, ensure_ascii=False)


def to_markdown(tasks, today: date | None = None) -> str:
    lines = [f"# To-Do List  ·  generated {datetime.now():%d %b %Y, %H:%M}", ""]
    for pr, icon in (("High", "🔴"), ("Medium", "🟠"), ("Low", "🟢")):
        group = [t for t in tasks if t["priority"] == pr]
        if not group:
            continue
        lines.append(f"## {icon} {pr} priority")
        for t in group:
            box = "x" if t["done"] else " "
            lines.append(f"- [{box}] **{t['task']}** - {fmt_deadline(t, today)} · {t['category']} · ~{t['est_minutes']} min")
        lines.append("")
    return "\n".join(lines)


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def to_ics(tasks) -> str:
    """All-day calendar events for every task that has a deadline (opens in Google/Outlook/Apple)."""
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//TaskPilot AI//EN", "CALSCALE:GREGORIAN"]
    for t in tasks:
        if not t["deadline"] or t["done"]:
            continue
        d = t["deadline"]
        out += [
            "BEGIN:VEVENT", f"UID:{t['id']}@taskpilot.ai", f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{d:%Y%m%d}", f"DTEND;VALUE=DATE:{(d + timedelta(days=1)):%Y%m%d}",
            f"SUMMARY:{_esc('[' + t['priority'] + '] ' + t['task'])}",
            f"DESCRIPTION:{_esc(t['reason'] or '')}", f"CATEGORIES:{t['category']}",
            "BEGIN:VALARM", "TRIGGER:-PT9H", "ACTION:DISPLAY", f"DESCRIPTION:{_esc(t['task'])}", "END:VALARM",
            "END:VEVENT",
        ]
    out.append("END:VCALENDAR")
    return "\r\n".join(out) + "\r\n"
