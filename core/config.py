"""Реестр моделей: воркеры и судьи по вендорам.

Ключевая идея демо: воркер и судья ВСЕГДА разных вендоров. Это не косметика —
ошибки моделей одного вендора коррелированы (общий стиль, общие слепые зоны),
поэтому судья «своего» вендора склонен одобрять «своего» воркера.
Кросс-вендорная проверка ломает эту корреляцию.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Model:
    id: str
    vendor: str
    price_in_per_1m: float     # $ за 1M входных токенов
    price_out_per_1m: float    # $ за 1M выходных токенов


# Цены сняты с https://openrouter.ai/api/v1/models на момент сборки демо.
# Воркеры — дешёвые модели разных вендоров.
WORKERS = [
    Model("anthropic/claude-haiku-5.5",            "anthropic", 0.100, 0.500),
    Model("google/gemini-2.5-flash-lite",          "google",    0.100, 0.400),
    Model("openai/gpt-4o-mini",                    "openai",    0.150, 0.600),
    Model("meta-llama/llama-3.3-70b-instruct",     "meta",      0.100, 0.320),
    Model("deepseek/deepseek-chat",                "deepseek",  0.257, 1.029),
]

# Судьи — сильнее и другого вендора, чем воркер.
JUDGES = [
    Model("deepseek/deepseek-chat",       "deepseek",  0.257, 1.029),
    Model("google/gemini-2.5-flash",      "google",    0.300, 2.500),
    Model("openai/gpt-4o-mini",           "openai",    0.150, 0.600),
]


def judge_for(worker: Model) -> Model:
    """Возвращает судью другого вендора (детерминированно, по кругу)."""
    candidates = [j for j in JUDGES if j.vendor != worker.vendor]
    if not candidates:
        raise ValueError(f"нет судьи другого вендора для {worker.vendor}")
    idx = sum(ord(c) for c in worker.id) % len(candidates)
    return candidates[idx]


def estimate_cost(model: Model, tokens_in: int, tokens_out: int) -> float:
    """Стоимость вызова в долларах."""
    return (tokens_in / 1_000_000) * model.price_in_per_1m + \
           (tokens_out / 1_000_000) * model.price_out_per_1m
