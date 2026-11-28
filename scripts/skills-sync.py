#!/usr/bin/env python3
"""Двусторонняя синхронизация личных скиллов Claude Code через приватный git-репозиторий.

~/.claude/skills/<имя>  <->  <репо>/skills/<имя>

Запускается хуками SessionStart и SessionEnd (ставит install-skills-sync.py).
Только стандартная библиотека. Никогда не роняет сессию: при любой ошибке пишет в лог и выходит с 0.

Правила:
- новый локальный скилл уезжает в репо, новый скилл из репо приезжает локально;
- правка побеждает там, где она сделана (сверка по хэшу последней синхронизации);
- правили с двух сторон: побеждает более свежий файл, проигравший кладётся в .sync-backup;
- удаления не разносятся: удалил на одном компьютере, на другом останется;
- не трогает synced/ (скиллы аккаунта claude.ai), симлинки, чужие git-клоны и всё из .syncignore;
- скилл с похожими на ключи строками или файлом .env не отправляется.
"""
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HOME = Path(os.environ.get("SKILLS_SYNC_HOME") or Path.home())
LOCAL = HOME / ".claude" / "skills"
REPO = Path(os.environ.get("SKILLS_REPO_DIR") or HOME / ".claude" / "skills-repo")
URL = os.environ.get("SKILLS_REPO_URL", "https://github.com/reymoff/claude-skills.git")
STATE = HOME / ".claude" / "skills-sync-state.json"
LOG = HOME / ".claude" / "skills-sync.log"
BACKUP = HOME / ".claude" / "skills-sync-backup"
JUNK = {"__pycache__", ".DS_Store", "node_modules", ".venv", ".git"}
MAX_BYTES = 20 * 1024 * 1024
SECRET = re.compile(
    rb"(sk-[A-Za-z0-9_\-]{24,}|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[0-9A-Z]{16}"
    rb"|xox[baprs]-[A-Za-z0-9\-]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    rb"|(?i:api[_-]?key|secret|token|password)\s*[:=]\s*[\"'][A-Za-z0-9_\-]{20,}[\"'])"
)


def log(msg):
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + msg
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass
    print("[skills-sync] " + msg, file=sys.stderr)


def git(*args, cwd=None, check=True):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    r = subprocess.run(["git", *args], cwd=cwd or REPO, env=env, capture_output=True, text=True, timeout=120)
    if check and r.returncode != 0:
        raise RuntimeError("git %s: %s" % (" ".join(args), (r.stderr or r.stdout).strip()[:300]))
    return r.stdout.strip()


def files(root):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in JUNK)
        for f in sorted(filenames):
            if f in JUNK or f.endswith(".pyc"):
                continue
            out.append(Path(dirpath) / f)
    return out


def digest(root):
    h = hashlib.sha256()
    for p in files(root):
        h.update(p.relative_to(root).as_posix().encode())
        h.update(b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def newest(root):
    return max((p.stat().st_mtime for p in files(root)), default=0)


def unsafe(root):
    """Причина, по которой скилл нельзя отправлять, или None."""
    total = 0
    for p in files(root):
        if p.name == ".env" or p.name.startswith(".env."):
            return "внутри файл %s" % p.name
        size = p.stat().st_size
        total += size
        if total > MAX_BYTES:
            return "больше 20 МБ"
        if size < 2 * 1024 * 1024 and SECRET.search(p.read_bytes()):
            return "в %s строка, похожая на ключ или пароль" % p.name
    return None


def copy(src, dst):
    tmp = dst.with_name(dst.name + ".sync-tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    shutil.copytree(src, tmp, ignore=shutil.ignore_patterns(*JUNK, "*.pyc"))
    if dst.exists():
        shutil.rmtree(dst)
    tmp.rename(dst)


def backup(path, name, side):
    dst = BACKUP / ("%s-%s-%s" % (name, side, time.strftime("%Y%m%d-%H%M%S")))
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(path, dst, ignore=shutil.ignore_patterns(*JUNK))
    return dst


def ignored_names():
    names = set()
    f = REPO / ".syncignore"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                names.add(line)
    return names


def account_names():
    """Скиллы, которые уже приезжают из аккаунта claude.ai: их локально не дублируем."""
    names = set()
    synced = LOCAL / "synced"
    if synced.is_dir():
        for p in synced.glob("*/*/SKILL.md"):
            names.add(p.parent.name)
        for p in synced.glob("*/SKILL.md"):
            names.add(p.parent.name)
    return names


def local_skills(skip):
    out = {}
    if not LOCAL.is_dir():
        return out
    for p in sorted(LOCAL.iterdir()):
        n = p.name
        if n.startswith(".") or n == "synced" or n in skip or n.endswith(".sync-tmp"):
            continue
        if p.is_symlink() or not p.is_dir() or not (p / "SKILL.md").is_file():
            continue
        if (p / ".git").exists():
            continue
        out[n] = p
    return out


def main():
    if shutil.which("git") is None:
        log("нет git, пропускаю")
        return
    if not (REPO / ".git").is_dir():
        REPO.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(["git", "clone", "-q", URL, str(REPO)], capture_output=True, text=True, timeout=180,
                           env=dict(os.environ, GIT_TERMINAL_PROMPT="0"))
        if r.returncode != 0:
            log("не смог склонировать %s: %s" % (URL, r.stderr.strip()[:200]))
            return
    has_remote_branch = bool(git("ls-remote", "--heads", "origin", check=False))
    if has_remote_branch:
        git("pull", "-q", "--rebase", "--autostash", check=False)

    skills_dir = REPO / "skills"
    skills_dir.mkdir(exist_ok=True)
    skip = ignored_names()
    in_account = account_names()
    try:
        state = json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}

    local = local_skills(skip)
    remote = {p.name: p for p in sorted(skills_dir.iterdir())
              if p.is_dir() and (p / "SKILL.md").is_file() and p.name not in skip}
    sent, received, skipped = [], [], []

    for name in sorted(set(local) | set(remote)):
        L, R = local.get(name), remote.get(name)
        if L and not R:
            why = unsafe(L)
            if why:
                skipped.append("%s (%s)" % (name, why))
                continue
            copy(L, skills_dir / name)
            state[name] = digest(L)
            sent.append(name)
        elif R and not L:
            if name in in_account:
                continue
            LOCAL.mkdir(parents=True, exist_ok=True)
            copy(R, LOCAL / name)
            state[name] = digest(R)
            received.append(name)
        else:
            hl, hr, last = digest(L), digest(R), state.get(name)
            if hl == hr:
                state[name] = hl
            elif last == hl:
                copy(R, L)
                state[name] = hr
                received.append(name)
            elif last == hr or newest(L) >= newest(R):
                why = unsafe(L)
                if why:
                    skipped.append("%s (%s)" % (name, why))
                    continue
                if last != hr:
                    log("конфликт %s: беру локальную, версия из репо в %s" % (name, backup(R, name, "repo")))
                copy(L, R)
                state[name] = hl
                sent.append(name)
            else:
                log("конфликт %s: беру версию из репо, локальная в %s" % (name, backup(L, name, "local")))
                copy(R, L)
                state[name] = hr
                received.append(name)

    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")

    git("add", "-A", "skills")
    if git("status", "--porcelain", "skills"):
        host = platform.node() or "pc"
        git("-c", "user.name=skills-sync", "-c", "user.email=skills-sync@local",
            "commit", "-q", "-m", "sync: %s (%s)" % (", ".join(sent) or "обновление", host))
        branch = git("rev-parse", "--abbrev-ref", "HEAD")
        r = subprocess.run(["git", "push", "-q", "-u", "origin", branch], cwd=REPO, capture_output=True, text=True,
                           timeout=120, env=dict(os.environ, GIT_TERMINAL_PROMPT="0"))
        if r.returncode != 0:
            log("не смог отправить, попробую в следующий раз: %s" % r.stderr.strip()[:200])
    if sent:
        log("отправил: " + ", ".join(sent))
    if received:
        log("получил: " + ", ".join(received))
    if skipped:
        log("НЕ отправил: " + "; ".join(skipped))
    if sent:
        print("[skills-sync] новые скиллы в репо: %s. Чтобы они появились в чате и на телефоне, "
              "скажи в чате Claude: синхронизируй скиллы" % ", ".join(sent), file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # хук не должен ломать сессию
        log("ошибка: %r" % (exc,))
    sys.exit(0)
