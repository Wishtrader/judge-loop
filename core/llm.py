"""Единый клиент к LLM через OpenRouter.

Один интерфейс на все вендоры — чтобы воркер и судья могли быть любой моделью
без ветвлений в коде. Считаем токены и деньги на каждом вызове: в демо важно
показать стоимость прогона, а не только результат.
"""
import json
import os
import time
import urllib.error
import urllib.request

from .config import Model, estimate_cost

API_URL = "https://openrouter.ai/api/v1/chat/completions"


class LLMResult:
    __slots__ = ("text", "tokens_in", "tokens_out", "cost_usd", "latency_s", "model_id", "error")

    def __init__(self, text, tokens_in, tokens_out, cost_usd, latency_s, model_id, error=None):
        self.text = text
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out
        self.cost_usd = cost_usd
        self.latency_s = latency_s
        self.model_id = model_id
        self.error = error


def _api_key() -> str:
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if key:
        return key
    # фолбэк: читаем из .env Hermes (только для локального демо)
    for path in ("/root/.hermes/.env", "/root/.hermes/profiles/xzx/.env"):
        try:
            for line in open(path, encoding="utf-8", errors="replace"):
                if line.startswith("OPENROUTER_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
        except OSError:
            continue
    raise RuntimeError("OPENROUTER_API_KEY не задан")


def call(model: Model, system: str, user: str, max_tokens: int = 1200,
         temperature: float = 0.0, retries: int = 3) -> LLMResult:
    """Один вызов модели с ретраями на 429/5xx.

    temperature=0 — важно для воспроизводимости демо: одинаковый вход даёт
    примерно одинаковый выход, иначе прогон на встрече может отличаться от
    прогона, который вы репетировали.
    """
    key = _api_key()
    payload = {
        "model": model.id,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    last_err = None
    for attempt in range(retries):
        started = time.time()
        try:
            req = urllib.request.Request(
                API_URL,
                data=json.dumps(payload).encode(),
                headers={"Authorization": f"Bearer {key}",
                         "Content-Type": "application/json",
                         "User-Agent": "judge-loop-demo"},
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.load(resp)
            latency = time.time() - started
            usage = data.get("usage", {}) or {}
            tin = int(usage.get("prompt_tokens", 0) or 0)
            tout = int(usage.get("completion_tokens", 0) or 0)
            msg = data["choices"][0]["message"]
            text = msg.get("content") or ""
            return LLMResult(text, tin, tout, estimate_cost(model, tin, tout),
                             latency, model.id)
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}"
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            return LLMResult("", 0, 0, 0.0, time.time() - started, model.id, last_err)
        except Exception as e:                      # таймауты, сети, парсинг
            last_err = f"{type(e).__name__}: {e}"
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            return LLMResult("", 0, 0, 0.0, time.time() - started, model.id, last_err)
    return LLMResult("", 0, 0, 0.0, 0.0, model.id, last_err)


def extract_code(text: str) -> str:
    """Достаёт код из ```python-блока, иначе возвращает текст как есть.

    Модели почти всегда оборачивают код в markdown-забор — если этого не
    обработать, pytest получит текст с ``` и упадёт на синтаксисе.
    """
    if "```" not in text:
        return text.strip()
    parts = text.split("```")
    # нечётные индексы — содержимое заборов
    for chunk in parts[1::2]:
        body = chunk
        if body.startswith("python"):
            body = body[len("python"):]
        elif body.startswith("py"):
            body = body[len("py"):]
        return body.strip()
    return text.strip()
