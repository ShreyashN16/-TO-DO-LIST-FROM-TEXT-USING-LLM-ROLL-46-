"""
test_core.py - offline tests (no API key, no internet needed).
Run:  python test_core.py
"""
from datetime import date

from core import (eisenhower_quadrant, extract_json, normalise_tasks, offline_extract,
                  resolve_deadline, sort_tasks, urgency_score)
from exporters import to_csv, to_ics, to_markdown
from prompts import build_messages
from samples import SAMPLES

TODAY = date(2026, 11, 22)  # a Sunday

TESTS = []


def test(fn):
    TESTS.append(fn)
    return fn


@test
def json_with_fences_and_chatter():
    d = extract_json('Sure! Here you go:\n```json\n{"tasks":[{"task":"a b"}],}\n```')
    assert d["tasks"][0]["task"] == "a b"


@test
def json_bare_list():
    assert extract_json('[{"task":"x y"}]') == {"tasks": [{"task": "x y"}]}


@test
def json_garbage_raises():
    try:
        extract_json("no json here")
    except ValueError:
        return
    raise AssertionError("should raise")


@test
def relative_dates():
    cases = {
        "today": date(2026, 11, 22), "tmrw": date(2026, 11, 23), "tomorrow": date(2026, 11, 23),
        "day after tomorrow": date(2026, 11, 24), "in 3 days": date(2026, 11, 25),
        "friday": date(2026, 11, 27), "by thursday": date(2026, 11, 26),
        "next week": date(2026, 11, 23), "end of month": date(2026, 11, 30),
        "30th": date(2026, 11, 30), "25 dec": date(2026, 12, 25), "dec 20": date(2026, 12, 20),
        "28/11": date(2026, 11, 28), "2026-12-01": date(2026, 12, 1), "in 2 weeks": date(2026, 12, 6),
        None: None, "null": None, "": None,
    }
    for text, want in cases.items():
        got = resolve_deadline(text, TODAY)
        assert got == want, f"{text!r}: got {got}, want {want}"


@test
def past_day_of_month_rolls_to_next_month():
    assert resolve_deadline("the 5th", TODAY) == date(2026, 12, 5)


@test
def normalise_cleans_and_dedupes():
    raw = {"tasks": [
        {"task": "submit report", "priority": "URGENT", "deadline": "tmrw", "category": "study"},
        {"task": "Submit report", "priority": "low"},
        {"task": "x"},
        "call mom",
        {"title": "pay fees", "priority": "p3", "deadline": "2026-11-30", "est_minutes": "abc"},
    ]}
    t = normalise_tasks(raw, TODAY)
    assert [x["task"] for x in t] == ["Submit report", "Call mom", "Pay fees"]
    assert t[0]["priority"] == "High" and t[0]["deadline"] == date(2026, 11, 23)
    assert t[0]["category"] == "Study" and t[1]["category"] == "Other"
    assert t[2]["priority"] == "Low" and t[2]["est_minutes"] == 30


@test
def sorting_priority_then_deadline_done_last():
    t = normalise_tasks({"tasks": [
        {"task": "low one", "priority": "Low"},
        {"task": "high later", "priority": "High", "deadline": "2026-12-10"},
        {"task": "high soon", "priority": "High", "deadline": "2026-11-23"},
        {"task": "medium", "priority": "Medium"},
    ]}, TODAY)
    t[2]["done"] = True
    order = [x["task"] for x in sort_tasks(t, "priority", TODAY)]
    assert order == ["High later", "Medium", "Low one", "High soon"], order


@test
def urgency_and_quadrants():
    t = normalise_tasks({"tasks": [
        {"task": "aa", "priority": "High", "deadline": "today"},
        {"task": "bb", "priority": "Low"},
    ]}, TODAY)
    assert urgency_score(t[0], TODAY) == 95 and urgency_score(t[1], TODAY) == 10
    assert eisenhower_quadrant(t[0], TODAY) == "Do first"
    assert eisenhower_quadrant(t[1], TODAY) == "Later"


@test
def offline_extractor_on_all_samples():
    for name, notes in SAMPLES.items():
        tasks = normalise_tasks(offline_extract(notes, TODAY), TODAY)
        assert len(tasks) >= 3, f"{name}: only {len(tasks)} tasks"
        assert any(x["priority"] == "High" for x in tasks), name


@test
def prompt_contains_today_and_few_shot():
    msgs = build_messages("buy milk", TODAY, "I am a student")
    assert "2026-11-22" in msgs[0]["content"] and "Sunday" in msgs[0]["content"]
    assert "student" in msgs[0]["content"]
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "user"]
    extract_json(msgs[2]["content"])  # the few-shot example itself must be valid JSON


@test
def exports_work():
    t = normalise_tasks({"tasks": [{"task": "Pay, bill; now", "priority": "High", "deadline": "tmrw"}]}, TODAY)
    assert "Pay, bill; now" in to_csv(t)
    assert "- [ ] **Pay, bill; now**" in to_markdown(t, TODAY)
    ics = to_ics(t)
    assert "DTSTART;VALUE=DATE:20261123" in ics and "Pay\\, bill\\; now" in ics


if __name__ == "__main__":
    passed = 0
    for fn in TESTS:
        try:
            fn()
            passed += 1
            print(f"  PASS  {fn.__name__}")
        except Exception as e:  # noqa
            print(f"  FAIL  {fn.__name__}: {e}")
    print(f"\n{passed}/{len(TESTS)} tests passed")
    raise SystemExit(0 if passed == len(TESTS) else 1)
