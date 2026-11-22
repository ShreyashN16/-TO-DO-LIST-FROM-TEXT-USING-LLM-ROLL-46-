"""
evaluate.py - run all 5 sample notes through a provider and print a results table
(use the numbers in your report's "Testing" section).

Examples:
  python evaluate.py --provider "Offline rules"
  python evaluate.py --provider Groq   --model openai/gpt-oss-120b      (needs GROQ_API_KEY)
  python evaluate.py --provider Gemini --model gemini-2.5-flash         (needs GEMINI_API_KEY)
"""
import argparse
import os
import time
from datetime import date

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from core import sort_tasks
from llm import PROVIDERS, extract_tasks
from samples import SAMPLES

# Hand-labelled ground truth: how many real tasks each sample contains
EXPECTED = {
    "🎓 Final-year student": 7, "💼 Busy intern": 6, "🏠 Home & errands": 6,
    "🏃 Health reset": 6, "🧠 Brain dump (very messy)": 8,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="Offline rules", choices=list(PROVIDERS))
    ap.add_argument("--model", default=None)
    ap.add_argument("--today", default=None, help="YYYY-MM-DD (default: real today)")
    ap.add_argument("--show", action="store_true", help="print every task")
    a = ap.parse_args()
    cfg = PROVIDERS[a.provider]
    model = a.model or cfg["models"][0]
    key = os.getenv(cfg["key_env"], "") if cfg["key_env"] else ""
    today = date.fromisoformat(a.today) if a.today else date.today()

    print(f"\nProvider: {a.provider} | Model: {model} | Today: {today}\n")
    print(f"{'Sample':30} {'Found':>5} {'Expect':>6} {'High':>4} {'w/ date':>7} {'Time(s)':>7} {'Fallback':>8}")
    print("-" * 76)
    tot_f = tot_e = 0
    for name, notes in SAMPLES.items():
        r = extract_tasks(notes, a.provider, key, model, today=today)
        hi = sum(t["priority"] == "High" for t in r.tasks)
        dated = sum(t["deadline"] is not None for t in r.tasks)
        tot_f += len(r.tasks)
        tot_e += EXPECTED[name]
        label = name.encode("ascii", "ignore").decode().strip()
        print(f"{label:30} {len(r.tasks):>5} {EXPECTED[name]:>6} {hi:>4} {dated:>7} {r.latency:>7.2f} "
              f"{'yes' if r.fell_back else 'no':>8}")
        if a.show:
            for t in sort_tasks(r.tasks, "priority", today):
                print(f"     [{t['priority'][0]}] {t['task']}  ->  {t['deadline'] or '-'}  ({t['category']})")
        if a.provider not in ("Offline rules", "Ollama (local)"):
            time.sleep(2)  # be gentle with free-tier rate limits
    print("-" * 76)
    print(f"Task recall (found / expected): {tot_f}/{tot_e} = {100 * min(tot_f, tot_e) / tot_e:.0f}%\n")


if __name__ == "__main__":
    main()
