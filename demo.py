"""Demo entrypoint — один запуск, всё демо.

    python demo.py                # все задачи × все воркеры
    python demo.py --workers 3    # только первые 3 модели (быстрее)
    python demo.py --tasks t01_slugify
"""
import argparse
import sys

from core.config import WORKERS
from core.report import print_results, save_artifacts
from core.runner import load_tasks, run_all


def main() -> int:
    ap = argparse.ArgumentParser(description="judge-loop demo")
    ap.add_argument("--workers", type=int, default=len(WORKERS),
                    help=f"сколько моделей-воркеров использовать (всего {len(WORKERS)})")
    ap.add_argument("--tasks", nargs="*", default=None,
                    help="id задач (по умолчанию все)")
    ap.add_argument("--jobs", type=int, default=8, help="параллельных потоков")
    args = ap.parse_args()

    tasks = load_tasks()
    if args.tasks:
        wanted = set(args.tasks)
        tasks = [t for t in tasks if t.id in wanted]
        if not tasks:
            print(f"нет таких задач: {args.tasks}", file=sys.stderr)
            return 2

    workers = WORKERS[:max(1, min(args.workers, len(WORKERS)))]

    print(f"Задач: {len(tasks)} · воркеров: {len(workers)} · пар: {len(tasks) * len(workers)}")
    print("Воркер и судья всегда разных вендоров — проверка кросс-вендорная.\n")
    for w in workers:
        from core.config import judge_for
        j = judge_for(w)
        print(f"  {w.id:44} → судья {j.id}")
    print("\nПрогон…")

    results = run_all(tasks, workers, jobs=args.jobs)
    print_results(results, tasks, workers)
    path = save_artifacts(results)
    print(f"\033[2mАртефакты: {path}\033[0m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
