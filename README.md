# ✅ TaskPilot AI: messy notes → prioritised to-do list

**PS 46 · To-Do List from Text** · LLM Mini Project

> People write messy notes. TaskPilot AI converts free-text notes into a prioritised to-do list with real deadlines.
> Paste notes → the LLM returns tasks as JSON (task, priority, deadline, …) → shown as a checklist (`st.checkbox` per task), sorted by priority.

![screenshot](screenshots/01_home.png)

## ✨ Features

| | Feature | Why it matters |
|---|---|---|
| 🧠 | **Any free LLM**: Groq (gpt-oss-120b), Gemini 2.5 Flash, any OpenAI-compatible API, or Ollama (local) | Free keys, no vendor lock-in |
| 🧾 | **Strict JSON output** with JSON mode + validation + a self-repair retry | The app never crashes on a bad reply |
| 📅 | **Real deadlines**: "tmrw", "next fri", "by 30th", "in 2 weeks" → `YYYY-MM-DD` | Today's date goes into the prompt, then Python double-checks it |
| 🔴🟠🟢 | **Priority + urgency score** (0–100) and sorting by priority, deadline or urgency | You know what to do first |
| ✅ | **Interactive checklist** (`st.checkbox` per task), progress bar, filters | The required feature, done well |
| 🧭 | **Eisenhower matrix** (Do first / Schedule / Delegate / Later) | Classic productivity framework |
| ⏱️ | **Today's focus plan**: fills your free hours with the most urgent tasks | Turns a list into a schedule |
| 📈 | **Timeline & workload charts** | See busy days at a glance |
| 🎙️ | **Voice notes** (Groq Whisper / Gemini) and `.txt` upload | Capture notes any way you like |
| ✏️ | **Editable table** to correct the AI, plus manual add / delete | A person can always fix the AI's output |
| ⬇️ | **Export** to CSV, Markdown, JSON and **.ics calendar** | Add deadlines to Google Calendar in one click |
| 🔍 | **Under the hood** tab: exact prompt, raw response, latency, tokens | Transparent, and easy to explain in the viva |
| 🛟 | **Offline fallback** (rule-based extractor) | The demo still works with no internet |

## 🚀 Run it

```bash

python -m venv venv && venv\Scripts\activate        # Windows   (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env                               # Mac/Linux: cp .env.example .env  → paste your key
streamlit run app.py
```

Free API keys: **Groq** → https://console.groq.com/keys · **Gemini** → https://aistudio.google.com/apikey
(You can also paste the key in the app sidebar instead of using `.env`.)

## 🧪 Tests

```bash
python test_core.py                                   # 11 offline tests (no key needed)
python evaluate.py --provider "Offline rules"         # baseline on 5 sample notes
python evaluate.py --provider Groq --show             # LLM results on the same 5 notes
```

## 🗂️ Project structure

```
app.py          Streamlit UI (checklist, matrix, timeline, editor, export, under-the-hood)
llm.py          Provider clients (Groq / Gemini / OpenAI-compatible / Ollama) + pipeline + voice
prompts.py      System prompt, few-shot example, repair prompt
core.py         JSON extraction, date resolver, validation, urgency score, sorting, offline extractor
exporters.py    CSV / Markdown / JSON / .ics calendar export
samples.py      5 messy sample notes
styles.py       Custom CSS theme
test_core.py    Offline unit tests
evaluate.py     Runs all samples through a provider and prints a results table
```

## 🔐 Security
The API key is read from `.env` or typed into the sidebar. It is never written to disk by the app, and `.env` is in `.gitignore`.
