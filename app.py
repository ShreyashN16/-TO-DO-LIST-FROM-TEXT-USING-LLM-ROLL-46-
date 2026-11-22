"""
TaskPilot AI - turn messy notes into a prioritised to-do list.
PS 46 · LLM Mini Project

Run:  streamlit run app.py
"""
from __future__ import annotations

import html
import os
import uuid
from datetime import date, datetime, time, timedelta

import altair as alt
import pandas as pd
import streamlit as st

try:  # optional: read keys from a local .env file
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from core import (CATEGORIES, PRIORITIES, days_left, eisenhower_quadrant, fmt_deadline,
                  resolve_deadline, sort_tasks, urgency_score)
from exporters import to_csv, to_ics, to_json, to_markdown
from llm import PROVIDERS, LLMError, extract_tasks, list_models, transcribe
from samples import SAMPLES
from styles import CSS

st.set_page_config(page_title="TaskPilot AI · Notes → To-Do", page_icon="✅",
                   layout="wide", initial_sidebar_state="expanded")
st.markdown(CSS, unsafe_allow_html=True)

ss = st.session_state
for k, v in {"tasks": [], "result": None, "history": [], "notes": "", "flash": None,
             "celebrate": False, "editor_ver": 0}.items():
    ss.setdefault(k, v)

CAT_ICON = {"Work": "💼", "Study": "📚", "Personal": "🏠", "Health": "💪",
            "Finance": "💳", "Errands": "🛒", "Other": "📌"}
PR_ICON = {"High": "🔴", "Medium": "🟠", "Low": "🟢"}
PR_COLOR = {"High": "#e5484d", "Medium": "#f0a020", "Low": "#30a46c"}


def esc(x) -> str:
    return html.escape(str(x or ""))


def secret(name: str) -> str:
    if not name:
        return ""
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.getenv(name, "")


def find(tid):
    return next((t for t in ss.tasks if t["id"] == tid), None)


# --------------------------------------------------------------------------- #
# Callbacks (run before the page re-renders, so they may change widget state)
# --------------------------------------------------------------------------- #
def cb_sample():
    pick = ss.get("sample_pick")
    if pick:
        ss.notes = SAMPLES[pick]


def cb_upload():
    f = ss.get("upload")
    if f is not None:
        ss.notes = f.getvalue().decode("utf-8", errors="ignore")
        ss.flash = ("success", f"Loaded {f.name}")


def cb_voice():
    audio = ss.get("voice")
    if audio is None:
        return
    try:
        text = transcribe(ss.provider, ss.get("api_key", ""), audio.getvalue(), ss.get("base_url"))
        ss.notes = (ss.notes.rstrip() + "\n" + text).strip()
        ss.flash = ("success", "🎙️ Voice note transcribed and added to your notes.")
    except LLMError as e:
        ss.flash = ("error", str(e))


def cb_toggle(tid):
    t = find(tid)
    if t:
        t["done"] = ss[f"done_{tid}"]
        if t["done"]:
            if all(x["done"] for x in ss.tasks):
                ss.celebrate = True
            else:
                ss.flash = ("toast", f"Nice! “{t['task']}” done ✅")


def cb_delete(tid):
    ss.tasks = [t for t in ss.tasks if t["id"] != tid]
    ss.pop(f"done_{tid}", None)


def cb_add():
    title = (ss.get("new_task") or "").strip()
    if len(title) < 2:
        ss.flash = ("error", "Type a task first.")
        return
    dl = None if ss.get("new_nodl") else ss.get("new_deadline")
    tid = uuid.uuid4().hex[:8]
    ss.tasks.append({"id": tid, "task": title[0].upper() + title[1:], "priority": ss.new_priority,
                     "deadline": dl, "deadline_text": "", "category": ss.new_category,
                     "est_minutes": int(ss.new_est), "reason": "Added manually", "source": "", "done": False})
    ss.new_task = ""
    ss.flash = ("toast", "Task added ➕")


def cb_apply_edits():
    ed = ss.get(f"editor_{ss.editor_ver}") or {}
    tasks = list(ss.tasks)
    colmap = {"Done": "done", "Task": "task", "Priority": "priority", "Deadline": "deadline",
              "Category": "category", "Est. min": "est_minutes", "Reason": "reason"}
    for idx, changes in ed.get("edited_rows", {}).items():
        t = tasks[int(idx)]
        for col, val in changes.items():
            field = colmap.get(col)
            if field == "deadline":
                val = resolve_deadline(val) if val else None
            if field == "est_minutes":
                val = int(val or 30)
            if field:
                t[field] = val
    for row in ed.get("added_rows", []):
        if not row.get("Task"):
            continue
        tasks.append({"id": uuid.uuid4().hex[:8], "task": row["Task"], "priority": row.get("Priority") or "Medium",
                      "deadline": resolve_deadline(row.get("Deadline")) if row.get("Deadline") else None,
                      "deadline_text": "", "category": row.get("Category") or "Other",
                      "est_minutes": int(row.get("Est. min") or 30), "reason": row.get("Reason") or "Added manually",
                      "source": "", "done": bool(row.get("Done"))})
    deleted = set(int(i) for i in ed.get("deleted_rows", []))
    ss.tasks = [t for i, t in enumerate(tasks) if i not in deleted]
    for t in ss.tasks:  # keep the checkboxes in sync
        ss[f"done_{t['id']}"] = t["done"]
    ss.editor_ver += 1
    ss.flash = ("toast", "Changes saved ✏️")


def cb_clear():
    for t in ss.tasks:
        ss.pop(f"done_{t['id']}", None)
    ss.tasks, ss.result = [], None


# --------------------------------------------------------------------------- #
# Sidebar - model settings
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.markdown('<div class="side-brand">Task<em>Pilot</em> AI</div>', unsafe_allow_html=True)
    st.caption("Messy notes in → prioritised plan out.")
    st.divider()

    provider = st.selectbox("🧠 LLM provider", list(PROVIDERS), key="provider",
                            help="Groq and Gemini have free API keys. Ollama runs a model on your laptop. "
                                 "'Offline rules' needs nothing and is the backup for the demo.")
    cfg = PROVIDERS[provider]

    base_in = None
    if provider in ("OpenAI-compatible", "Ollama (local)"):
        base_in = st.text_input("Base URL", value=cfg["base_url"], key=f"base_in_{provider}",
                                help="Any OpenAI-style endpoint ending in /v1 (OpenRouter, Together, your "
                                     "college's free AI gateway, LM Studio...).")
    key_in = ""
    if cfg["needs_key"]:
        key_in = st.text_input("API key", value=secret(cfg["key_env"]), type="password",
                               key=f"key_in_{provider}", help="Kept only in this browser session, never saved to disk.")
        if cfg["key_url"]:
            st.caption(f"No key? [Get a free one ↗]({cfg['key_url']})")
    # plain (non-widget) copies that callbacks can read
    ss.api_key, ss.base_url = (key_in or "").strip(), (base_in or "").strip() or None

    options = ss.get(f"models_{provider}") or cfg["models"]
    mc1, mc2 = st.columns([5, 1], vertical_alignment="bottom")
    model = mc1.selectbox("Model", options, key=f"model_{provider}")
    if mc2.button("↻", help="Fetch the live model list from the provider"):
        try:
            found = list_models(provider, ss.get("api_key", ""), ss.get("base_url"))
            if found:
                ss[f"models_{provider}"] = found
                ss.flash = ("toast", f"Found {len(found)} models")
                st.rerun()
        except LLMError as e:
            st.error(str(e))
    custom = st.text_input("…or type any model name", key=f"custom_model_{provider}", placeholder="optional")
    model = custom.strip() or model

    st.divider()
    user_context = st.text_input("👤 About you (helps prioritise)", value="Final-year engineering student",
                                 key="user_context")
    today = st.date_input("📆 Treat today as", value=date.today(), format="DD/MM/YYYY", key="today",
                          help="The AI resolves 'tmrw', 'next fri', 'by 25th' relative to this date.")
    fallback = st.toggle("🛟 Auto-fallback to offline rules", value=True,
                         help="If the API fails (no internet, rate limit), the app still produces a list.")
    st.divider()
    st.caption("Built with Streamlit · Groq / Gemini / Ollama  \nPS 46 · LLM Mini Project")

needs_key_missing = cfg["needs_key"] and not ss.get("api_key")

# --------------------------------------------------------------------------- #
# Hero
# --------------------------------------------------------------------------- #
dot_cls = "dot off" if needs_key_missing else "dot"
status = f"{esc(provider)} · {esc(model)}" + (" · add an API key in the sidebar" if needs_key_missing else " · ready")
st.markdown(f"""
<div class="hero">
  <div class="steps">
    <div class="step"><b>① Paste</b>messy notes</div>
    <div class="step"><b>② Extract</b>LLM → JSON</div>
    <div class="step"><b>③ Act</b>tick &amp; export</div>
  </div>
  <h1>Task<em>Pilot</em> AI</h1>
  <p>Brain-dump your scattered notes, chats and reminders. TaskPilot pulls out every task,
  works out real deadlines and ranks them, so you know exactly what to do first.</p>
  <div class="pill"><span class="{dot_cls}"></span>{status}</div>
</div>""", unsafe_allow_html=True)

if ss.flash:
    kind, msg = ss.flash
    ss.flash = None
    if kind == "toast":
        st.toast(msg)
    else:
        getattr(st, kind)(msg)
if ss.celebrate:
    st.balloons()
    st.toast("🎉 Everything done! Take a break.")
    ss.celebrate = False

# --------------------------------------------------------------------------- #
# Input
# --------------------------------------------------------------------------- #
left, right = st.columns([3, 2], gap="large")
with left:
    st.markdown('<div class="sec">Paste your messy notes</div>'
                '<div class="sub">WhatsApp reminders, class notes, a brain dump: anything goes.</div>',
                unsafe_allow_html=True)
    st.pills("Try a sample", list(SAMPLES), key="sample_pick", on_change=cb_sample,
             label_visibility="collapsed")
    st.text_area("Notes", key="notes", height=245, label_visibility="collapsed",
                 placeholder="e.g. submit DBMS assignment tmrw!! pay hostel fees before 30th, "
                             "call mom tonight, maybe clean room sometime…")
    words = len(ss.notes.split())
    st.caption(f"{words} words · {len(ss.notes)} characters")

with right:
    st.markdown('<div class="sec">…or speak / upload them</div>'
                '<div class="sub">Voice uses Groq Whisper or Gemini.</div>', unsafe_allow_html=True)
    st.audio_input("Record a voice note", key="voice", on_change=cb_voice)
    st.file_uploader("Upload a .txt / .md file", type=["txt", "md"], key="upload", on_change=cb_upload)
    with st.container(key="go"):
        go = st.button("✨ Organise my notes", key="go_btn")

if go:
    if not ss.notes.strip():
        st.warning("Paste some notes first, or pick a sample above.")
    elif needs_key_missing and not fallback:
        st.error(f"Add your {provider} API key in the sidebar, or choose 'Offline rules'.")
    else:
        use_provider = "Offline rules" if needs_key_missing else provider
        with st.status("Reading your notes…", expanded=True) as status_box:
            st.write(f"🧩 Building the prompt: rules + one worked example + today = {today:%a %d %b %Y}")
            st.write(f"🧠 Asking **{use_provider}** ({model if use_provider == provider else 'rule-based'}) for JSON…")
            res = extract_tasks(ss.notes, use_provider, ss.get("api_key", ""), model, ss.get("base_url"),
                                user_context, today, fallback)
            st.write(f"🔎 Parsed and validated {len(res.tasks)} tasks · resolved deadlines · removed duplicates")
            status_box.update(label=f"Done: {len(res.tasks)} tasks in {res.latency:.1f}s",
                              state="error" if res.fell_back else "complete", expanded=False)
        for t in ss.tasks:
            ss.pop(f"done_{t['id']}", None)
        ss.tasks, ss.result = res.tasks, res
        ss.editor_ver += 1
        ss.history.append({
            "Time": datetime.now().strftime("%H:%M:%S"), "Provider": res.provider, "Model": res.model,
            "Tasks": len(res.tasks), "Latency (s)": round(res.latency, 2), "Tokens": res.tokens,
            "Attempts": res.attempts, "Fallback": "Yes" if res.fell_back else "No",
        })
        if needs_key_missing:
            ss.flash = ("info", "No API key found, so the offline rule-based extractor was used. "
                                "Add a Groq or Gemini key in the sidebar for AI-quality results.")
            st.rerun()

# --------------------------------------------------------------------------- #
# Results
# --------------------------------------------------------------------------- #
tasks = ss.tasks
if not tasks:
    st.markdown('<div class="empty"><b>Your prioritised list will appear here</b>'
                'Pick a sample above and press <i>Organise my notes</i>.</div>', unsafe_allow_html=True)
    st.markdown('<div class="foot">TaskPilot AI · PS 46 · LLM Mini Project</div>', unsafe_allow_html=True)
    st.stop()

res = ss.result
active = [t for t in tasks if not t["done"]]
n_done = len(tasks) - len(active)
n_high = sum(t["priority"] == "High" for t in active)
n_soon = sum(1 for t in active if (d := days_left(t, today)) is not None and 0 <= d <= 2)
n_over = sum(1 for t in active if (d := days_left(t, today)) is not None and d < 0)
effort = sum(t["est_minutes"] for t in active)

st.markdown(f"""
<div class="stats">
  <div class="stat"><div class="k">Tasks</div><div class="v">{len(tasks)}</div></div>
  <div class="stat hi"><div class="k">High priority</div><div class="v">{n_high}</div></div>
  <div class="stat warn"><div class="k">Due ≤ 2 days</div><div class="v">{n_soon}</div></div>
  <div class="stat hi"><div class="k">Overdue</div><div class="v">{n_over}</div></div>
  <div class="stat ok"><div class="k">Completed</div><div class="v">{n_done}/{len(tasks)}</div></div>
  <div class="stat"><div class="k">Effort left</div><div class="v">{effort / 60:.1f}h</div></div>
</div>""", unsafe_allow_html=True)

if res and res.summary:
    st.markdown(f'<div class="summary"><b>AI plan ·</b> {esc(res.summary)}</div>', unsafe_allow_html=True)
if res and res.fell_back:
    st.markdown(f'<div class="warnbox">⚠️ The model call failed ({esc(res.error)}). '
                f'Showing the offline rule-based result so you are never stuck.</div>', unsafe_allow_html=True)
st.progress(n_done / len(tasks), text=f"{round(100 * n_done / len(tasks))}% complete")

tab_list, tab_matrix, tab_time, tab_edit, tab_hood, tab_export = st.tabs(
    ["✅ Checklist", "🧭 Priority matrix", "📅 Timeline & day plan", "✏️ Edit", "🔍 Under the hood", "⬇️ Export"])


def card_html(t) -> str:
    d = days_left(t, today)
    dl_cls = "over" if d is not None and d < 0 else ("today" if d == 0 else "")
    chips = [
        f'<span class="chip {t["priority"]}">{PR_ICON[t["priority"]]} {t["priority"]}</span>',
        f'<span class="chip {dl_cls}">📅 {esc(fmt_deadline(t, today))}</span>',
        f'<span class="chip">{CAT_ICON.get(t["category"], "📌")} {esc(t["category"])}</span>',
        f'<span class="chip">⏱ ~{t["est_minutes"]} min</span>',
    ]
    why = esc(t["reason"])
    if t.get("source"):
        why += f' · <i>from “{esc(t["source"])}”</i>'
    return (f'<div class="ttl {"done" if t["done"] else ""}">{esc(t["task"])}</div>'
            f'<div class="chips">{"".join(chips)}</div>'
            + (f'<div class="why">💡 {why}</div>' if why else ""))


def render_task(t):
    k = f"done_{t['id']}"
    if k not in ss:
        ss[k] = t["done"]
    with st.container(key=f"card_{t['priority']}_{t['id']}{'_done' if t['done'] else ''}"):
        c1, c2, c3, c4 = st.columns([0.45, 8, 1.1, 0.6], vertical_alignment="center")
        c1.checkbox("Done", key=k, on_change=cb_toggle, args=(t["id"],), label_visibility="collapsed")
        c2.markdown(card_html(t), unsafe_allow_html=True)
        c3.markdown(f'<div class="score">{urgency_score(t, today)}<small>URGENCY</small></div>',
                    unsafe_allow_html=True)
        c4.button("✕", key=f"del_{t['id']}", on_click=cb_delete, args=(t["id"],), help="Remove this task")


# ---- Checklist ------------------------------------------------------------- #
with tab_list:
    f1, f2, f3 = st.columns([2, 2, 3])
    view = f1.segmented_control("Show", ["Active", "All", "Done"], default="Active", key="view") or "All"
    sort_label = f2.selectbox("Sort by", ["Priority", "Deadline", "Urgency score"], key="sort")
    present = [c for c in CATEGORIES if any(t["category"] == c for t in tasks)]
    cats = f3.multiselect("Category", present, key="cats", placeholder="All categories")

    shown = [t for t in tasks if (view == "All") or (view == "Done") == t["done"]]
    if cats:
        shown = [t for t in shown if t["category"] in cats]
    mode = {"Priority": "priority", "Deadline": "deadline", "Urgency score": "urgency"}[sort_label]
    shown = sort_tasks(shown, mode, today)

    if not shown:
        st.info("Nothing here. 🎉" if view == "Active" else "No tasks match these filters.")
    elif mode == "priority":
        for pr in PRIORITIES:
            group = [t for t in shown if t["priority"] == pr]
            if not group:
                continue
            st.markdown(f'<div class="grouphead">{PR_ICON[pr]} {pr} priority <span class="n">{len(group)}</span>'
                        f'<span class="bar"></span></div>', unsafe_allow_html=True)
            for t in group:
                render_task(t)
    else:
        for t in shown:
            render_task(t)

    with st.expander("➕ Add a task manually"):
        with st.form("add_form", clear_on_submit=False, border=False):
            a1, a2 = st.columns([3, 1])
            a1.text_input("Task", key="new_task", placeholder="e.g. Print the project report")
            a2.selectbox("Priority", PRIORITIES, index=1, key="new_priority")
            b1, b2, b3, b4 = st.columns([2, 1, 2, 1], vertical_alignment="bottom")
            b1.date_input("Deadline", value=today + timedelta(days=1), key="new_deadline", format="DD/MM/YYYY")
            b2.checkbox("No deadline", key="new_nodl")
            b3.selectbox("Category", CATEGORIES, key="new_category")
            b4.number_input("Minutes", 5, 600, 30, step=5, key="new_est")
            st.form_submit_button("Add task", on_click=cb_add, type="primary")

    st.button("🗑️ Clear all tasks", on_click=cb_clear, type="tertiary")

# ---- Eisenhower matrix ----------------------------------------------------- #
with tab_matrix:
    st.markdown('<div class="sub">The Eisenhower matrix: <b>urgent</b> = due within 2 days, '
                '<b>important</b> = High priority. Do the top-left box first.</div>', unsafe_allow_html=True)
    quads = {"Do first": [], "Schedule": [], "Delegate": [], "Later": []}
    for t in sort_tasks(active, "urgency", today):
        quads[eisenhower_quadrant(t, today)].append(t)
    meta = [("Do first", "q1", "🔥 Do first", "Urgent and important"),
            ("Schedule", "q2", "🗓️ Schedule", "Important, not urgent: block time for it"),
            ("Delegate", "q3", "🤝 Quick wins / delegate", "Urgent, less important"),
            ("Later", "q4", "🌱 Later", "Neither: do it when you're free")]
    cells = []
    for name, cls, title, hint in meta:
        items = "".join(f'<div class="qi">{esc(t["task"])}<span>{esc(fmt_deadline(t, today))}</span></div>'
                        for t in quads[name]) or '<div class="hint">Nothing here</div>'
        cells.append(f'<div class="quad {cls}"><h4>{title} · {len(quads[name])}</h4>'
                     f'<div class="hint">{hint}</div>{items}</div>')
    st.markdown(f'<div class="matrix">{"".join(cells)}</div>', unsafe_allow_html=True)

# ---- Timeline + day plan --------------------------------------------------- #
with tab_time:
    dated = [t for t in active if t["deadline"]]
    tcol, pcol = st.columns([3, 2], gap="large")
    with tcol:
        st.markdown('<div class="sec">Deadline timeline</div>', unsafe_allow_html=True)
        if dated:
            df = pd.DataFrame([{"Task": t["task"], "Deadline": pd.Timestamp(t["deadline"]),
                                "Priority": t["priority"], "Minutes": t["est_minutes"],
                                "When": fmt_deadline(t, today)} for t in dated])
            color = alt.Color("Priority:N", scale=alt.Scale(domain=PRIORITIES,
                              range=[PR_COLOR[p] for p in PRIORITIES]), legend=alt.Legend(orient="top"))
            order = df.sort_values("Deadline")["Task"].tolist()
            pts = alt.Chart(df).mark_circle(size=260, opacity=.9).encode(
                x=alt.X("Deadline:T", title=None, axis=alt.Axis(format="%d %b", grid=True)),
                y=alt.Y("Task:N", sort=order, title=None, axis=alt.Axis(labelLimit=260)),
                color=color, tooltip=["Task", "Priority", "When", "Minutes"])
            rule = alt.Chart(pd.DataFrame({"d": [pd.Timestamp(today)]})).mark_rule(
                color="#5b5bd6", strokeDash=[5, 4], size=2).encode(x="d:T")
            st.altair_chart((rule + pts).properties(height=max(220, 34 * len(df))))

            st.markdown('<div class="sec">Workload by day</div>', unsafe_allow_html=True)
            df["Day"] = df["Deadline"].dt.strftime("%d %b")
            day_order = df.sort_values("Deadline")["Day"].drop_duplicates().tolist()
            bars = alt.Chart(df).mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6).encode(
                x=alt.X("Day:N", sort=day_order, title=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("sum(Minutes):Q", title="Minutes of work"), color=color,
                tooltip=["Task", "Minutes", "Priority"])
            st.altair_chart(bars.properties(height=220))
        else:
            st.info("None of the active tasks has a deadline.")
        undated = len(active) - len(dated)
        if undated:
            st.caption(f"{undated} active task(s) have no deadline and are not shown.")

    with pcol:
        st.markdown('<div class="sec">Today’s focus plan</div>'
                    '<div class="sub">Fills your free hours with the most urgent tasks first.</div>',
                    unsafe_allow_html=True)
        p1, p2 = st.columns(2)
        hours = p1.slider("Free hours today", 1.0, 10.0, 4.0, 0.5)
        start = p2.time_input("Start at", value=time(9, 0), step=timedelta(minutes=15))
        budget, clock, slots, left_out = hours * 60, datetime.combine(today, start), [], []
        for t in sort_tasks(active, "urgency", today):
            if t["est_minutes"] <= budget:
                end = clock + timedelta(minutes=t["est_minutes"])
                slots.append((clock, end, t))
                budget -= t["est_minutes"] + 10
                clock = end + timedelta(minutes=10)  # 10-minute break between tasks
            else:
                left_out.append(t)
        if slots:
            st.markdown("".join(
                f'<div class="slot"><div class="t">{a:%H:%M}–{b:%H:%M}</div>'
                f'<div class="b {t["priority"]}">{esc(t["task"])}<span>{t["est_minutes"]} min · '
                f'{esc(fmt_deadline(t, today))}</span></div></div>' for a, b, t in slots), unsafe_allow_html=True)
        else:
            st.info("No task fits into the time you have. Try more hours.")
        if left_out:
            st.caption(f"Doesn't fit today: {', '.join(t['task'] for t in left_out[:4])}"
                       + ("…" if len(left_out) > 4 else ""))

# ---- Edit table ------------------------------------------------------------ #
with tab_edit:
    st.markdown('<div class="sub">Fix anything the AI got wrong, add rows at the bottom, or delete rows, '
                'then press <b>Save changes</b>.</div>', unsafe_allow_html=True)
    edf = pd.DataFrame([{
        "Done": t["done"], "Task": t["task"], "Priority": t["priority"], "Deadline": t["deadline"],
        "Category": t["category"], "Est. min": t["est_minutes"], "Reason": t["reason"],
    } for t in tasks])
    st.data_editor(
        edf, key=f"editor_{ss.editor_ver}", num_rows="dynamic", hide_index=True,
        column_config={
            "Done": st.column_config.CheckboxColumn(width="small"),
            "Task": st.column_config.TextColumn(width="large", required=True),
            "Priority": st.column_config.SelectboxColumn(options=PRIORITIES, required=True),
            "Deadline": st.column_config.DateColumn(format="DD MMM YYYY"),
            "Category": st.column_config.SelectboxColumn(options=CATEGORIES),
            "Est. min": st.column_config.NumberColumn(min_value=5, max_value=600, step=5),
            "Reason": st.column_config.TextColumn(width="medium"),
        })
    st.button("💾 Save changes", on_click=cb_apply_edits, type="primary")

# ---- Under the hood (great for the viva) ----------------------------------- #
with tab_hood:
    if res:
        h = st.columns(5)
        h[0].metric("Provider", res.provider)
        h[1].metric("Model", (res.model or "-")[:22])
        h[2].metric("Latency", f"{res.latency:.2f}s")
        h[3].metric("Tokens", res.tokens if res.tokens else "-")
        h[4].metric("Attempts", res.attempts, help="2 = the JSON was invalid once and the model was asked to repair it")
        st.markdown("**Pipeline:** notes → prompt (system rules + few-shot example + today's date) → LLM in JSON mode "
                    "→ `extract_json()` → `normalise_tasks()` (schema check, date resolution, dedupe) "
                    "→ `sort_tasks()` → UI")
        with st.expander("📜 Exact prompt sent to the model", expanded=False):
            for m in res.messages:
                st.markdown(f"**{m['role'].upper()}**")
                st.code(m["content"], language="markdown", wrap_lines=True)
        with st.expander("🧾 Raw model response", expanded=True):
            st.code(res.raw or "(no response)", language="json", wrap_lines=True)
        with st.expander("✅ Validated JSON used by the app"):
            st.code(to_json(tasks), language="json")
    if ss.history:
        st.markdown('<div class="sec">Run history (this session)</div>', unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(ss.history), hide_index=True)

# ---- Export ---------------------------------------------------------------- #
with tab_export:
    st.markdown('<div class="sub">Take your list anywhere. The calendar file adds every deadline '
                'to Google Calendar, Outlook or Apple Calendar.</div>', unsafe_allow_html=True)
    stamp = f"{today:%Y%m%d}"
    e1, e2, e3, e4 = st.columns(4)
    e1.download_button("📊 CSV (Excel)", to_csv(tasks), f"todo_{stamp}.csv", "text/csv")
    e2.download_button("📝 Markdown", to_markdown(tasks, today), f"todo_{stamp}.md", "text/markdown")
    e3.download_button("🧩 JSON", to_json(tasks), f"todo_{stamp}.json", "application/json")
    e4.download_button("📅 Calendar (.ics)", to_ics(tasks), f"todo_{stamp}.ics", "text/calendar")
    st.markdown("**Preview / copy**")
    st.code(to_markdown(tasks, today), language="markdown")

st.markdown('<div class="foot">TaskPilot AI · PS 46 · LLM Mini Project · '
            'AI output can be wrong, so check deadlines before relying on them.</div>', unsafe_allow_html=True)
