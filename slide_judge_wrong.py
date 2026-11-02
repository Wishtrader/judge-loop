#!/usr/bin/env python3
"""Слайд 1920x1080: случай, где LLM-судья ошибся.

Тёмная тема, моноширинный код, крупный шрифт — чтобы читалось через видеозвонок.
"""
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
BG = (13, 15, 20)
FG = (232, 236, 244)
DIM = (138, 148, 166)
GREEN = (74, 222, 128)
RED = (248, 113, 113)
AMBER = (251, 191, 36)
CYAN = (34, 211, 238)
PANEL = (22, 26, 34)
BORDER = (45, 52, 66)

SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
SANS_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
MONO_B = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

def f(path, size):
    return ImageFont.truetype(path, size)

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

# ── заголовок ─────────────────────────────────────────────
d.text((80, 56), "СУДЬЯ ОШИБСЯ", font=f(SANS_B, 30), fill=AMBER)
d.text((80, 100), "Проверка собственного гейта", font=f(SANS_B, 54), fill=FG)
d.text((80, 172), "Задача: парсер длительности  ·  писал Gemini (Google)  ·  проверял GPT (OpenAI)",
       font=f(SANS, 23), fill=DIM)

# разделитель
d.line([(80, 218), (W - 80, 218)], fill=BORDER, width=2)

# ── левая колонка: код ────────────────────────────────────
LX = 80
d.text((LX, 246), "КОД", font=f(SANS_B, 20), fill=CYAN)

code_lines = [
    ("def parse_duration(text: str) -> int:", FG),
    ("    if not text:", FG),
    ("        raise ValueError(\"empty\")", FG),
    ("", FG),
    ("    matches = re.findall(r'(\\d+)([hms])', text)", FG),
    ("", FG),
    ("    if not matches:", FG),
    ("        raise ValueError(f\"Invalid: {text}\")", FG),
    ("    # проверка, что разобрана вся строка", DIM),
    ("    if parsed_length != len(text):", FG),
    ("        raise ValueError(f\"Invalid: {text}\")", FG),
    ("    ...", DIM),
]

py = 288
for line, color in code_lines:
    d.text((LX, py), line, font=f(MONO, 21), fill=color)
    py += 32

# зелёная полоса слева от кода
d.rectangle([(LX - 14, 286), (LX - 8, py - 8)], fill=GREEN)

# ── левая колонка: тесты ──────────────────────────────────
d.text((LX, py + 34), "ТЕСТЫ", font=f(SANS_B, 20), fill=CYAN)
d.text((LX, py + 68), "13 / 13 — все прошли", font=f(MONO_B, 26), fill=GREEN)

# ── правая колонка: утверждение судьи ─────────────────────
RX = 1010
d.text((RX, 246), "ЧТО СКАЗАЛ СУДЬЯ", font=f(SANS_B, 20), fill=CYAN)

# панель с цитатой
box = [(RX, 284), (W - 80, 470)]
d.rounded_rectangle(box, radius=12, fill=PANEL, outline=RED, width=2)
d.text((RX + 24, 306), "«Код не обрабатывает случаи", font=f(SANS, 23), fill=FG)
d.text((RX + 24, 340), "с некорректными единицами,", font=f(SANS, 23), fill=FG)
d.text((RX + 24, 374), "например '1x', что может", font=f(SANS, 23), fill=FG)
d.text((RX + 24, 408), "привести к ошибкам.»", font=f(SANS, 23), fill=FG)
d.text((RX + 24, 442), "— вердикт: reject, 4.00 / 5", font=f(MONO, 19), fill=RED)

# ── правая колонка: фактическая проверка ──────────────────
d.text((RX, 510), "ЧТО ПРОИСХОДИТ НА САМОМ ДЕЛЕ", font=f(SANS_B, 20), fill=CYAN)

probe = [
    ("'1x'",   "ValueError OK"),
    ("'abc'",  "ValueError OK"),
    ("''",     "ValueError OK"),
    ("'10'",   "ValueError OK"),
    ("'h'",    "ValueError OK"),
]
py2 = 552
for arg, res in probe:
    d.text((RX + 24, py2), arg, font=f(MONO, 22), fill=FG)
    d.text((RX + 140, py2), "→", font=f(MONO, 22), fill=DIM)
    d.text((RX + 180, py2), res, font=f(MONO_B, 22), fill=GREEN)
    py2 += 34

d.text((RX, py2 + 18), "Код корректен. Дефекта нет.", font=f(SANS_B, 24), fill=AMBER)

# ── нижний вывод ──────────────────────────────────────────
d.line([(80, 880), (W - 80, 880)], fill=BORDER, width=2)

d.text((80, 906), "ВЫВОД", font=f(SANS_B, 20), fill=CYAN)
d.text((80, 942),
       "Тесты — точны, но проверяют только то, что предусмотрел автор тестов.",
       font=f(SANS, 25), fill=FG)
d.text((80, 980),
       "Судья — шире по охвату, но может выдумать дефект, которого нет.",
       font=f(SANS, 25), fill=FG)
d.text((80, 1022),
       "Расхождение между гейтами — не приговор, а сигнал: посмотреть глазами.",
       font=f(SANS_B, 25), fill=AMBER)

img.save("/root/judge-loop/JUDGE_WAS_WRONG.png", optimize=True)
print("saved /root/judge-loop/JUDGE_WAS_WRONG.png", img.size)
