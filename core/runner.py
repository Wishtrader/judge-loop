"""Оркестратор: параллельный прогон воркеров, тестов и судей.

Поток на одну пару (задача × воркер):
  1. воркер генерирует код
  2. pytest проверяет код (объективный гейт)
  3. судья другого вендора оценивает качество (субъективный гейт)
  4. итог = тесты зелёные И судья approve

Всё параллельно через ThreadPoolExecutor: 15 пар отрабатывают за время
одной-двух самых медленных, а не суммой всех вызовов.
"""
import concurrent.futures as cf
import json
import os
import time
from dataclasses import dataclass, field

from .config import Model, WORKERS, judge_for
from .judge import judge, JudgeOutcome
from .llm import call, extract_code
from .verifier import run_tests, TestOutcome

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASKS_DIR = os.path.join(ROOT, "tasks")
TESTS_DIR = os.path.join(ROOT, "tests")

WORKER_SYSTEM = """Ты — инженер, который пишет продовый код по спецификации.
Требования к ответу:
- Верни ТОЛЬКО код в одном блоке ```python ... ```, без пояснений до и после.
- Код должен содержать ровно ту функцию, которая указана в задании, с точно такой сигнатурой.
- Никаких вызовов input(), print(), сетевых запросов и чтения файлов.
- Обработай краевые случаи, перечисленные в критериях приёмки.
- Если по заданию нужен ValueError — поднимай именно ValueError."""


@dataclass
class TaskSpec:
    id: str
    title: str
    function_name: str
    spec: str
    acceptance: list[str]
    min_score: float = 3.5


@dataclass
class RunResult:
    task: TaskSpec
    worker: Model
    judge_model: Model
    code: str = ""
    gen_error: str | None = None
    gen_cost: float = 0.0
    gen_latency: float = 0.0
    tests: TestOutcome | None = None
    judge_out: JudgeOutcome | None = None
    total_cost: float = 0.0
    total_latency: float = 0.0
    notes: list[str] = field(default_factory=list)

    @property
    def approved(self) -> bool:
        return (self.gen_error is None
                and self.tests is not None and self.tests.ok
                and self.judge_out is not None and self.judge_out.verdict == "approve")

    @property
    def gate_status(self) -> str:
        if self.gen_error:
            return "GEN-FAIL"
        if self.tests is None or not self.tests.ok:
            return "TESTS-FAIL"
        if self.judge_out is None or self.judge_out.verdict != "approve":
            return "JUDGE-REJECT"
        return "APPROVED"


def load_tasks() -> list[TaskSpec]:
    out = []
    for name in sorted(os.listdir(TASKS_DIR)):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(TASKS_DIR, name), encoding="utf-8") as f:
            d = json.load(f)
        out.append(TaskSpec(
            id=d["id"], title=d["title"], function_name=d["function_name"],
            spec=d["spec"], acceptance=d.get("acceptance", []),
            min_score=float(d.get("min_score", 3.5)),
        ))
    return out


def load_test_source(task: TaskSpec) -> str:
    path = os.path.join(TESTS_DIR, f"{task.id}.py")
    with open(path, encoding="utf-8") as f:
        return f.read()


def run_one(task: TaskSpec, worker: Model) -> RunResult:
    jm = judge_for(worker)
    res = RunResult(task=task, worker=worker, judge_model=jm)

    user_prompt = (
        f"Задание: {task.title}\n\n"
        f"Спецификация:\n{task.spec}\n\n"
        "Критерии приёмки:\n" + "\n".join(f"- {a}" for a in task.acceptance) +
        f"\n\nНужна функция с именем `{task.function_name}`. "
        "Верни только код в блоке ```python."
    )

    gen = call(worker, WORKER_SYSTEM, user_prompt, max_tokens=900)
    res.gen_cost = gen.cost_usd
    res.gen_latency = gen.latency_s
    if gen.error:
        res.gen_error = gen.error
        res.total_cost = gen.cost_usd
        res.total_latency = gen.latency_s
        return res

    res.code = extract_code(gen.text)
    if not res.code.strip():
        res.gen_error = "пустой ответ"
        return res

    # Гейт 1: объективные тесты
    res.tests = run_tests(res.code, load_test_source(task), task.function_name)
    test_summary = (f"{res.tests.passed}/{res.tests.total} тестов пройдено"
                    if res.tests.total else "тесты не запустились")

    # Гейт 2: кросс-вендорный судья
    res.judge_out = judge(jm, task.title, task.spec, task.acceptance,
                          res.code, test_summary, min_score=task.min_score)

    res.total_cost = gen.cost_usd + (res.judge_out.cost_usd or 0.0)
    res.total_latency = gen.latency_s + (res.judge_out.latency_s or 0.0)
    return res


def run_all(tasks: list[TaskSpec], workers: list[Model], jobs: int = 8) -> list[RunResult]:
    pairs = [(t, w) for t in tasks for w in workers]
    results: list[RunResult] = []
    started = time.time()
    with cf.ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {pool.submit(run_one, t, w): (t, w) for t, w in pairs}
        for fut in cf.as_completed(futures):
            t, w = futures[fut]
            try:
                results.append(fut.result())
            except Exception as e:                     # не роняем весь прогон из-за одной пары
                r = RunResult(task=t, worker=w, judge_model=judge_for(w))
                r.gen_error = f"внутренняя ошибка: {type(e).__name__}: {e}"
                results.append(r)
    elapsed = time.time() - started
    for r in results:
        r.wall_elapsed = elapsed
    return results
