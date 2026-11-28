#!/usr/bin/env python3
"""Ставит синхронизацию скиллов на этот компьютер. Повторный запуск безопасен.

    python3 scripts/install-skills-sync.py            (macOS, Linux)
    python  scripts\\install-skills-sync.py            (Windows)

Что делает:
1. кладёт skills-sync.py в ~/.claude/
2. добавляет хуки SessionStart и SessionEnd в ~/.claude/settings.json (остальное в файле не трогает)
3. дописывает правило про скиллы в ~/.claude/CLAUDE.md
4. запускает первую синхронизацию
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HOME = Path(os.environ.get("SKILLS_SYNC_HOME") or Path.home())
CLAUDE = HOME / ".claude"
SRC = Path(__file__).resolve().parent / "skills-sync.py"
DST = CLAUDE / "skills-sync.py"
MARK = "<!-- skills-sync -->"
RULE = MARK + """
## Скиллы: одно место для всех устройств

- Новый личный скилл создавай в `~/.claude/skills/<имя>/SKILL.md`. В папку `synced/` не пиши: это копия скиллов аккаунта claude.ai, она только для чтения.
- Синхронизацию между компьютерами делает `~/.claude/skills-sync.py` (хуки в начале и в конце сессии). После создания или правки скилла запусти его сам, чтобы не ждать конца сессии.
- В чат и на телефон скилл попадает только через аккаунт claude.ai. Если в сессии есть инструмент `propose_skills`, сразу покажи владельцу карточку скилла. Если его нет, напомни одной строкой: скажи в чате Claude "синхронизируй скиллы".
- Ключи, пароли и токены в скиллы не клади: такой скилл синхронизация не отправит.
""" + MARK + "\n"


def main():
    CLAUDE.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SRC, DST)

    py = Path(sys.executable).as_posix()
    cmd = '"%s" "%s"' % (py, DST.as_posix())
    settings_path = CLAUDE / "settings.json"
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        settings = {}
    if settings_path.exists():
        shutil.copyfile(settings_path, settings_path.with_name("settings.json.bak-skills-sync"))
    hooks = settings.setdefault("hooks", {})
    for event in ("SessionStart", "SessionEnd"):
        groups = hooks.setdefault(event, [])
        for g in groups:
            g["hooks"] = [h for h in g.get("hooks", []) if "skills-sync.py" not in h.get("command", "")]
        groups[:] = [g for g in groups if g.get("hooks")]
        groups.append({"hooks": [{"type": "command", "command": cmd, "timeout": 120}]})
    settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = CLAUDE / "CLAUDE.md"
    text = md.read_text(encoding="utf-8") if md.exists() else ""
    if MARK in text:
        head, _, rest = text.partition(MARK)
        _, _, tail = rest.partition(MARK)
        text = head + RULE + tail.lstrip("\n")
    else:
        text = (text.rstrip("\n") + "\n\n" if text.strip() else "") + RULE
    md.write_text(text, encoding="utf-8")

    print("Хуки и правило на месте. Первая синхронизация...")
    subprocess.run([sys.executable, str(DST)])
    print("Готово. Лог: %s" % (CLAUDE / "skills-sync.log"))


if __name__ == "__main__":
    main()
