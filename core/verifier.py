"""Детерминированный верификатор: прогон реальных тестов на сгенерированном коде.

Зачем отдельно от LLM-судьи: судью можно уговорить. Он читает код и «понимает
замысел» — и прощает краевые случаи, которые ломают прод. Тест не прощает.
Поэтому гейт двойной: сначала тесты (объективно), потом судья (качество).

Каждый прогон изолирован: отдельная временная директория, свой процесс,
жёсткий таймаут, без доступа к сети.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile


class TestOutcome:
    __slots__ = ("passed", "total", "failed", "returncode", "output", "timeout")

    def __init__(self, passed, total, failed, returncode, output, timeout=False):
        self.passed = passed
        self.total = total
        self.failed = failed
        self.returncode = returncode
        self.output = output
        self.timeout = timeout

    @property
    def ok(self) -> bool:
        return not self.timeout and self.returncode == 0 and self.total > 0 \
               and self.passed == self.total


_COUNT_RE = re.compile(r"(\d+) (passed|failed|error|errors)")


def _test_python() -> str:
    """Интерпретатор, в котором есть pytest.

    Нельзя полагаться на sys.executable: демо может запускаться из окружения
    Hermes, где pytest не установлен. Порядок: переменная окружения →
    локальный .venv проекта → текущий интерпретатор.
    """
    explicit = os.getenv("JUDGE_LOOP_PYTHON")
    if explicit and os.path.exists(explicit):
        return explicit
    local = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         ".venv", "bin", "python")
    if os.path.exists(local):
        return local
    return sys.executable


def run_tests(code: str, test_source: str, function_name: str,
              timeout: int = 25) -> TestOutcome:
    """Кладём сгенерированный код и тесты рядом, запускаем pytest."""
    workdir = tempfile.mkdtemp(prefix="jloop_")
    try:
        # Сгенерированный код: имя модуля = имя функции, ожидаемое тестами
        with open(os.path.join(workdir, f"{function_name}.py"), "w", encoding="utf-8") as f:
            f.write(code)
        with open(os.path.join(workdir, "test_gen.py"), "w", encoding="utf-8") as f:
            f.write(test_source)

        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "PYTHONPATH": workdir,
            "PYTHONDONTWRITEBYTECODE": "1",
            "HOME": workdir,
            "NO_PROXY": "*",      # режем сеть: сгенерированный код не должен никуда ходить
            "no_proxy": "*",
        }
        try:
            proc = subprocess.run(
                [_test_python(), "-m", "pytest", "test_gen.py", "-q", "--no-header",
                 "-p", "no:cacheprovider"],
                cwd=workdir, env=env, capture_output=True, text=True, timeout=timeout,
            )
            out = (proc.stdout or "") + (proc.stderr or "")
            rc = proc.returncode
            timed_out = False
        except subprocess.TimeoutExpired as e:
            out = f"TIMEOUT после {timeout}s\n{e.stdout or ''}"
            rc = -1
            timed_out = True

        counts = dict((kind, int(n)) for n, kind in _COUNT_RE.findall(out))
        passed = counts.get("passed", 0)
        failed = counts.get("failed", 0) + counts.get("error", 0) + counts.get("errors", 0)
        total = passed + failed
        return TestOutcome(passed, total, failed, rc, out[-4000:], timed_out)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
