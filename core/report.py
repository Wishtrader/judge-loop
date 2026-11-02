"""Отчёт: таблица прогона в терминал + сохранение артефактов.

Печатаем три вещи, которые решают на встрече:
  1. Кто прошёл гейт, а кто нет — с причиной отказа
  2. Сколько это стоило и сколько заняло
  3. Сводку по моделям: у какой какой процент прохождения
"""
import json
import os
import time

from .config import Model
from .runner import RunResult, TaskSpec

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTIFACTS = os.path.join(ROOT, "artifacts")

# без внешних зависимостей: ANSI-цвета вручную
G = "\033[32m"; R = "\033[31m"; Y = "\033[33m"; B = "\033[36m"; DIM = "\033[2m"; RST = "\033[0m"


def _short(model_id: str, width: int = 26) -> str:
    return model_id if len(model_id) <= width else model_id[:width - 1] + "…"


def print_results(results: list[RunResult], tasks: list[TaskSpec], workers: list[Model]) -> None:
    by_pair = {(r.task.id, r.worker.id): r for r in results}

    print()
    print(f"{B}{'ЗАДАЧА':<14}{'ВОРКЕР':<27}{'СУДЬЯ':<24}{'ТЕСТЫ':<9}{'ОЦЕНКА':<9}{'ГЕЙТ':<14}{RST}")
    print("─" * 97)
    for t in tasks:
        for w in workers:
            r = by_pair.get((t.id, w.id))
            if not r:
                continue
            tests = "—" if r.tests is None else f"{r.tests.passed}/{r.tests.total}"
            score = "—" if not r.judge_out or not r.judge_out.scores else f"{r.judge_out.score:.2f}"
            status = r.gate_status
            color = G if status == "APPROVED" else (Y if status == "JUDGE-REJECT" else R)
            print(f"{t.id:<14}{_short(w.id):<27}{_short(r.judge_model.id):<24}"
                  f"{tests:<9}{score:<9}{color}{status:<14}{RST}")

    total_cost = sum(r.total_cost for r in results)
    approved = sum(1 for r in results if r.approved)
    wall = getattr(results[0], "wall_elapsed", 0.0) if results else 0.0
    print("─" * 97)
    print(f"  прошло гейт: {approved}/{len(results)}   "
          f"стоимость: ${total_cost:.5f}   "
          f"время: {wall:.1f}s (параллельно)")
    print()

    # сводка по воркерам
    print(f"{B}СВОДКА ПО ВОРКЕРАМ{RST}")
    print(f"  {'модель':<36}{'прошло':<10}{'ср. оценка':<13}{'$':<12}")
    for w in workers:
        rs = [r for r in results if r.worker.id == w.id]
        if not rs:
            continue
        ap = sum(1 for r in rs if r.approved)
        scores = [r.judge_out.score for r in rs if r.judge_out and r.judge_out.scores]
        avg = sum(scores) / len(scores) if scores else 0.0
        cost = sum(r.total_cost for r in rs)
        print(f"  {_short(w.id, 35):<36}{ap}/{len(rs):<8}{avg:<13.2f}${cost:<11.5f}")
    print()

    # отказы с причинами — это и есть доказательство, что гейт работает
    rejects = [r for r in results if not r.approved]
    if rejects:
        print(f"{B}ПОЧЕМУ ОТКЛОНЕНО (гейт в действии){RST}")
        for r in rejects[:12]:
            if r.gen_error:
                why = f"ошибка генерации: {r.gen_error}"
            elif r.tests and not r.tests.ok:
                failed_line = next((ln.strip() for ln in r.tests.output.splitlines()
                                    if "failed" in ln.lower() or "Error" in ln), "")
                why = f"тесты {r.tests.passed}/{r.tests.total} — {failed_line[:70]}"
            elif r.judge_out and r.judge_out.verdict != "approve":
                why = f"судья {r.judge_out.score:.2f}: {r.judge_out.reason[:70]}"
            else:
                why = "неизвестно"
            print(f"  {Y}{r.task.id}{RST} × {_short(r.worker.id, 24)}: {why}")
        print()


def save_artifacts(results: list[RunResult]) -> str:
    os.makedirs(ARTIFACTS, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(ARTIFACTS, f"run_{stamp}.json")
    payload = {
        "timestamp": stamp,
        "total_cost_usd": round(sum(r.total_cost for r in results), 6),
        "wall_elapsed_s": round(getattr(results[0], "wall_elapsed", 0.0), 2) if results else 0,
        "approved": sum(1 for r in results if r.approved),
        "total": len(results),
        "runs": [{
            "task": r.task.id,
            "worker": r.worker.id,
            "worker_vendor": r.worker.vendor,
            "judge": r.judge_model.id,
            "judge_vendor": r.judge_model.vendor,
            "cross_vendor": r.worker.vendor != r.judge_model.vendor,
            "gate": r.gate_status,
            "tests": None if r.tests is None else {
                "passed": r.tests.passed, "total": r.tests.total,
                "ok": r.tests.ok, "timeout": r.tests.timeout},
            "judge_scores": (r.judge_out.scores if r.judge_out else None),
            "judge_reason": (r.judge_out.reason if r.judge_out else None),
            "cost_usd": round(r.total_cost, 6),
            "code": r.code,
        } for r in results],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path
