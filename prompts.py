"""prompts.py - the prompt sent to the LLM (kept in one place for the report / viva)."""
from datetime import date

SYSTEM_PROMPT = """You are TaskPilot, an expert productivity assistant.
Your job: read messy, informal notes and turn them into a clean, prioritised to-do list.

TODAY is {today_iso} ({weekday}). Resolve every relative date ("tmrw", "next fri",
"by the 25th", "end of week", "in 3 days") into an absolute date in YYYY-MM-DD format
using TODAY as the reference. If a note gives no time hint, deadline must be null.
Never invent a deadline that is not implied by the notes.

RULES
1. One task = one concrete action. Split compound sentences ("buy milk and call mom" -> 2 tasks).
2. Start every task with a verb, keep it under 12 words, fix spelling, keep names/numbers.
3. Ignore chatter that is not an action (feelings, greetings, past events).
4. Merge duplicates.
5. priority must be exactly "High", "Medium" or "Low":
   - High   : due within 2 days, OR words like urgent/asap/must/important, OR exams,
              submissions, payments, health or anything with a penalty if missed.
   - Medium : has a deadline later than 2 days, or is clearly needed but not urgent.
   - Low    : optional / "maybe" / "someday" / nice-to-have, no deadline pressure.
6. category must be one of: Work, Study, Personal, Health, Finance, Errands, Other.
7. est_minutes: realistic integer estimate of effort.
8. reason: <= 12 words explaining the priority.
9. source: the exact fragment of the notes the task came from (<= 15 words).

Return ONLY valid JSON, no markdown, matching this schema:
{{
  "tasks": [
    {{
      "task": "string",
      "priority": "High | Medium | Low",
      "deadline": "YYYY-MM-DD or null",
      "deadline_text": "the original time words, or empty string",
      "category": "Work | Study | Personal | Health | Finance | Errands | Other",
      "est_minutes": 30,
      "reason": "string",
      "source": "string"
    }}
  ],
  "summary": "one friendly sentence summarising the plan"
}}"""

FEW_SHOT_USER = """Notes:
ugh so much to do. dbms assignment due tmrw!! also maybe watch that ML video sometime.
pay hostel fees before 30th and call dad on sunday"""

FEW_SHOT_ASSISTANT_TEMPLATE = """{{"tasks":[
{{"task":"Submit DBMS assignment","priority":"High","deadline":"{tmrw}","deadline_text":"tmrw","category":"Study","est_minutes":120,"reason":"Graded submission due tomorrow","source":"dbms assignment due tmrw!!"}},
{{"task":"Pay hostel fees","priority":"High","deadline":"{d30}","deadline_text":"before 30th","category":"Finance","est_minutes":15,"reason":"Payment with a fixed due date","source":"pay hostel fees before 30th"}},
{{"task":"Call dad","priority":"Medium","deadline":"{sun}","deadline_text":"sunday","category":"Personal","est_minutes":20,"reason":"Planned personal commitment","source":"call dad on sunday"}},
{{"task":"Watch the ML video","priority":"Low","deadline":null,"deadline_text":"","category":"Study","est_minutes":45,"reason":"Optional, marked maybe/sometime","source":"maybe watch that ML video sometime"}}
],"summary":"Finish the DBMS assignment first, then clear the fees before the 30th."}}"""

REPAIR_PROMPT = """Your previous reply was not valid JSON for the required schema.
Error: {error}
Reply again with ONLY the JSON object, nothing else."""


def build_messages(notes: str, today: date, user_context: str = "") -> list[dict]:
    """Chat messages: system rules + one worked example (few-shot) + the real notes."""
    from core import resolve_deadline

    tmrw = resolve_deadline("tomorrow", today)
    sun = resolve_deadline("sunday", today)
    d30 = resolve_deadline("30th", today)
    system = SYSTEM_PROMPT.format(today_iso=today.isoformat(), weekday=today.strftime("%A"))
    if user_context.strip():
        system += f"\n\nABOUT THE USER (use to judge priority): {user_context.strip()}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": FEW_SHOT_USER},
        {"role": "assistant", "content": FEW_SHOT_ASSISTANT_TEMPLATE.format(
            tmrw=tmrw.isoformat(), sun=sun.isoformat(), d30=d30.isoformat())},
        {"role": "user", "content": f"Notes:\n{notes.strip()}"},
    ]
