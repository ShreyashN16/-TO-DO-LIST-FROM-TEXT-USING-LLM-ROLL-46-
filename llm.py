"""
llm.py - one tiny client for every free LLM option, using plain `requests`
(no vendor SDKs, so installation is just `pip install -r requirements.txt`).

Providers
  * Groq            - OpenAI-compatible API, very fast, free tier
  * Gemini          - Google AI Studio free tier, native JSON mode
  * OpenAI-compatible - any service that offers a base URL + key
                      (OpenRouter, Together, a college/"free AI" gateway, LM Studio...)
  * Ollama          - local model on your laptop, no key, works offline
  * Offline rules   - no model at all (backup for the demo)
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date

import requests

from core import extract_json, normalise_tasks, offline_extract
from prompts import REPAIR_PROMPT, build_messages

TIMEOUT = 60

PROVIDERS = {
    "Groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "models": ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.6-27b"],
        "needs_key": True, "key_env": "GROQ_API_KEY",
        "key_url": "https://console.groq.com/keys",
    },
    "Gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "models": ["gemini-2.5-flash", "gemini-flash-latest", "gemini-2.5-flash-lite"],
        "needs_key": True, "key_env": "GEMINI_API_KEY",
        "key_url": "https://aistudio.google.com/apikey",
    },
    "OpenAI-compatible": {
        "base_url": "https://openrouter.ai/api/v1",
        "models": ["openai/gpt-oss-20b:free"],
        "needs_key": True, "key_env": "OPENAI_COMPAT_API_KEY",
        "key_url": "",
    },
    "Ollama (local)": {
        "base_url": "http://localhost:11434",
        "models": ["llama3.2", "qwen2.5:3b", "gemma3:4b"],
        "needs_key": False, "key_env": "", "key_url": "https://ollama.com/download",
    },
    "Offline rules": {
        "base_url": "", "models": ["rule-based"], "needs_key": False, "key_env": "", "key_url": "",
    },
}


class LLMError(RuntimeError):
    pass


@dataclass
class Result:
    tasks: list
    summary: str = ""
    raw: str = ""
    provider: str = ""
    model: str = ""
    latency: float = 0.0
    tokens: int | None = None
    attempts: int = 1
    fell_back: bool = False
    error: str = ""
    messages: list = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Low-level calls
# --------------------------------------------------------------------------- #
def _raise_for(r: requests.Response, who: str):
    if r.status_code >= 400:
        try:
            msg = r.json().get("error", r.text)
            if isinstance(msg, dict):
                msg = msg.get("message", str(msg))
        except Exception:
            msg = r.text[:300]
        if r.status_code in (401, 403):
            raise LLMError(f"{who}: invalid or missing API key ({r.status_code}). {msg}")
        if r.status_code == 429:
            raise LLMError(f"{who}: rate limit reached (free tier). Wait a minute or switch model. {msg}")
        if r.status_code == 404:
            raise LLMError(f"{who}: model not found - pick another model. {msg}")
        raise LLMError(f"{who} error {r.status_code}: {msg}")


def _openai_chat(base_url, key, model, messages, json_mode=True, extra=None):
    url = base_url.rstrip("/") + "/chat/completions"
    body = {"model": model, "messages": messages, "temperature": 0.2}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    if extra:
        body.update(extra)
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    r = requests.post(url, json=body, headers=headers, timeout=TIMEOUT)
    if r.status_code == 400 and (json_mode or extra):
        # some models reject response_format / reasoning params -> retry plain
        body.pop("response_format", None)
        for k in (extra or {}):
            body.pop(k, None)
        r = requests.post(url, json=body, headers=headers, timeout=TIMEOUT)
    _raise_for(r, "API")
    data = r.json()
    text = data["choices"][0]["message"].get("content") or ""
    tokens = (data.get("usage") or {}).get("total_tokens")
    return text, tokens


def _gemini_chat(base_url, key, model, messages):
    system = "\n".join(m["content"] for m in messages if m["role"] == "system")
    contents = [
        {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
        for m in messages if m["role"] != "system"
    ]
    url = f"{base_url}/models/{model}:generateContent"
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
    }
    r = requests.post(url, json=body, headers={"x-goog-api-key": key}, timeout=TIMEOUT)
    _raise_for(r, "Gemini")
    data = r.json()
    try:
        text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
    except (KeyError, IndexError):
        raise LLMError(f"Gemini returned no text (maybe blocked): {str(data)[:200]}")
    tokens = (data.get("usageMetadata") or {}).get("totalTokenCount")
    return text, tokens


def _ollama_chat(base_url, model, messages):
    r = requests.post(
        base_url.rstrip("/") + "/api/chat",
        json={"model": model, "messages": messages, "stream": False, "format": "json",
              "options": {"temperature": 0.2}},
        timeout=180,
    )
    _raise_for(r, "Ollama")
    data = r.json()
    return data["message"]["content"], data.get("eval_count")


def chat(provider: str, key: str, model: str, messages: list, base_url: str | None = None):
    cfg = PROVIDERS[provider]
    base = (base_url or cfg["base_url"]).strip()
    try:
        if provider == "Gemini":
            return _gemini_chat(base, key, model, messages)
        if provider == "Ollama (local)":
            return _ollama_chat(base, model, messages)
        extra = {"reasoning_effort": "low"} if "gpt-oss" in model and provider == "Groq" else None
        return _openai_chat(base, key, model, messages, extra=extra)
    except requests.exceptions.ConnectionError:
        hint = " Is Ollama running? (ollama serve)" if provider.startswith("Ollama") else " Check your internet."
        raise LLMError(f"Could not connect to {provider}.{hint}")
    except requests.exceptions.Timeout:
        raise LLMError(f"{provider} timed out after {TIMEOUT}s.")


def list_models(provider: str, key: str, base_url: str | None = None) -> list[str]:
    """Ask the provider which models are live right now (model names change often)."""
    cfg = PROVIDERS[provider]
    base = (base_url or cfg["base_url"]).rstrip("/")
    try:
        if provider == "Gemini":
            r = requests.get(f"{base}/models", headers={"x-goog-api-key": key}, timeout=20)
            _raise_for(r, "Gemini")
            return sorted(
                m["name"].split("/", 1)[1] for m in r.json().get("models", [])
                if "generateContent" in m.get("supportedGenerationMethods", []) and "gemini" in m["name"]
            )
        if provider == "Ollama (local)":
            r = requests.get(f"{base}/api/tags", timeout=10)
            _raise_for(r, "Ollama")
            return [m["name"] for m in r.json().get("models", [])]
        if provider == "Offline rules":
            return ["rule-based"]
        r = requests.get(f"{base}/models", headers={"Authorization": f"Bearer {key}"}, timeout=20)
        _raise_for(r, provider)
        skip = ("whisper", "tts", "guard", "embed", "orpheus", "safeguard")
        return sorted(m["id"] for m in r.json().get("data", []) if not any(s in m["id"] for s in skip))
    except requests.exceptions.RequestException as e:
        raise LLMError(f"Could not list models: {e}")


def transcribe(provider: str, key: str, audio_bytes: bytes, base_url: str | None = None) -> str:
    """Voice notes -> text. Groq uses Whisper, Gemini uses its audio understanding."""
    import base64
    if provider == "Groq":
        r = requests.post(
            (base_url or PROVIDERS["Groq"]["base_url"]).rstrip("/") + "/audio/transcriptions",
            headers={"Authorization": f"Bearer {key}"},
            files={"file": ("voice.wav", audio_bytes, "audio/wav")},
            data={"model": "whisper-large-v3-turbo", "response_format": "json"},
            timeout=TIMEOUT,
        )
        _raise_for(r, "Groq Whisper")
        return r.json().get("text", "").strip()
    if provider == "Gemini":
        url = f"{PROVIDERS['Gemini']['base_url']}/models/gemini-2.5-flash:generateContent"
        body = {"contents": [{"role": "user", "parts": [
            {"text": "Transcribe this voice note exactly. Return only the transcript."},
            {"inline_data": {"mime_type": "audio/wav", "data": base64.b64encode(audio_bytes).decode()}},
        ]}]}
        r = requests.post(url, json=body, headers={"x-goog-api-key": key}, timeout=TIMEOUT)
        _raise_for(r, "Gemini")
        return "".join(p.get("text", "") for p in r.json()["candidates"][0]["content"]["parts"]).strip()
    raise LLMError("Voice input needs Groq or Gemini selected in the sidebar.")


# --------------------------------------------------------------------------- #
# The full pipeline: notes -> prompt -> LLM -> JSON -> validated tasks
# --------------------------------------------------------------------------- #
def extract_tasks(notes: str, provider: str, key: str = "", model: str = "",
                  base_url: str | None = None, user_context: str = "",
                  today: date | None = None, fallback: bool = True) -> Result:
    today = today or date.today()
    messages = build_messages(notes, today, user_context)

    if provider == "Offline rules":
        t0 = time.time()
        data = offline_extract(notes, today)
        return Result(normalise_tasks(data, today), data["summary"], raw=str(data),
                      provider=provider, model="rule-based", latency=time.time() - t0, messages=messages)

    t0, attempts, last_err, raw = time.time(), 0, "", ""
    tokens_total = 0
    convo = list(messages)
    for attempts in (1, 2):  # 1 normal try + 1 self-repair try
        try:
            raw, tokens = chat(provider, key, model, convo, base_url)
            tokens_total += tokens or 0
            data = extract_json(raw)
            tasks = normalise_tasks(data, today)
            if not tasks and notes.strip():
                raise ValueError("Model returned zero tasks")
            return Result(tasks, str(data.get("summary", "")), raw, provider, model,
                          time.time() - t0, tokens_total or None, attempts, messages=messages)
        except LLMError as e:
            last_err = str(e)
            break  # network / key problems will not be fixed by re-asking
        except ValueError as e:
            last_err = str(e)
            convo = convo + [{"role": "assistant", "content": raw or "(empty)"},
                             {"role": "user", "content": REPAIR_PROMPT.format(error=e)}]

    if not fallback:
        raise LLMError(last_err)
    data = offline_extract(notes, today)
    return Result(normalise_tasks(data, today), data["summary"], raw, provider, model,
                  time.time() - t0, tokens_total or None, attempts, fell_back=True,
                  error=last_err, messages=messages)
