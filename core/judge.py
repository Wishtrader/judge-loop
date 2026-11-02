"""LLM-судья: оценивает качество того, что тесты пропустили.

Тесты отвечают на вопрос «работает ли». Судья — «хорошо ли сделано»:
читаемость, идиоматичность, обработка краевых случаев, которых нет в тестах,
риски в проде. Судья обязан вернуть СТРОГИЙ JSON — иначе результат
недетерминирован и его нельзя использовать как гейт.
"""
import json
import re

from .config import Model
from .llm import call, extract_code

JUDGE_SYSTEM = """Ты — строгий ревьюер кода в CI-конвейере. Твоя задача — не хвалить, а находить проблемы.
Оцениваешь решение по трём критериям, каждый от 1 до 5:
- correctness: верно ли решает задачу, включая краевые случаи которых нет в тестах
- robustness: что сломается в проде (пустой вход, None, огромные значения, типы)
- clarity: читаемо ли, идиоматично ли для Python

Правила:
- 5 ставь редко. 3 — «средне, но приемлемо». 1-2 — есть реальная проблема.
- Если код не соответствует контракту функции (неверное имя, неверная сигнатура) — correctness = 1.
- Если код падает на пустом входе, а по заданию должен вернуть значение — robustness <= 2.

Отвечай ТОЛЬКО валидным JSON без markdown-забора:
{"correctness": N, "robustness": N, "clarity": N, "verdict": "approve"|"reject", "reason": "одно предложение на русском"}"""


class JudgeOutcome:
    __slots__ = ("verdict", "scores", "reason", "raw", "error", "cost_usd", "model_id", "latency_s")

    def __init__(self, verdict, scores, reason, raw, error, cost_usd, model_id, latency_s):
        self.verdict = verdict
        self.scores = scores
        self.reason = reason
        self.raw = raw
        self.error = error
        self.cost_usd = cost_usd
        self.model_id = model_id
        self.latency_s = latency_s

    @property
    def score(self) -> float:
        """Средний балл 1..5."""
        if not self.scores:
            return 0.0
        vals = [self.scores.get(k, 0) for k in ("correctness", "robustness", "clarity")]
        return round(sum(vals) / len(vals), 2)


def _parse_json(text: str) -> dict | None:
    """Достаёт JSON даже если модель обернула его в ```json ... ```."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # последняя попытка: вытащить первый {...}
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return None


def judge(judge_model: Model, task_title: str, spec: str, acceptance: list[str],
          code: str, test_summary: str, min_score: float = 3.5) -> JudgeOutcome:
    user = f"""Задача: {task_title}

Спецификация:
{spec}

Критерии приёмки:
""" + "\n".join(f"- {a}" for a in acceptance) + f"""

Результат автопроверки тестами: {test_summary}

Код на ревью:
```python
{code}
```

Верни только JSON по заданной схеме."""

    res = call(judge_model, JUDGE_SYSTEM, user, max_tokens=400)
    if res.error:
        return JudgeOutcome("error", {}, f"судья недоступен: {res.error}", "",
                            res.error, res.cost_usd, judge_model.id, res.latency_s)

    data = _parse_json(res.text)
    if not data:
        return JudgeOutcome("error", {}, "судья вернул не-JSON", res.text[:400],
                            "invalid_json", res.cost_usd, judge_model.id, res.latency_s)

    scores = {k: int(data.get(k, 0) or 0)
              for k in ("correctness", "robustness", "clarity")}
    avg = sum(scores.values()) / 3
    raw_verdict = str(data.get("verdict", "")).lower()
    # Гейт: вердикт модели и его же баллы должны согласоваться.
    # Если модель написала approve, но баллы ниже порога — верим баллам.
    verdict = "approve" if (raw_verdict == "approve" and avg >= min_score) else "reject"

    return JudgeOutcome(verdict, scores, str(data.get("reason", ""))[:300],
                        res.text[:400], None, res.cost_usd, judge_model.id, res.latency_s)
