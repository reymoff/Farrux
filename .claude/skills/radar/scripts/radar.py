#!/usr/bin/env python3
"""radar: глаза и уши для анализа конкурентов (YouTube, Instagram, любой сайт из yt-dlp).

  radar.py watch <url|файл> [--frames 24] [--lang ru] [--no-audio]
  radar.py scan  <url канала или @ник IG> [--limit 30]
  radar.py ingest <json из Graph API business_discovery>
  radar.py dash

Всё складывает в ./radar (или $RADAR_HOME). Платных API нет.
Переменные: RADAR_COOKIES=chrome|firefox|edge (куки из браузера для Instagram и закрытого YouTube),
RADAR_WHISPER_MODEL=small|medium|путь к своей модели CTranslate2.
"""
import argparse, datetime as dt, html, json, os, re, shutil, statistics, subprocess, sys, urllib.request
from pathlib import Path

HOME = Path(os.environ.get("RADAR_HOME", "radar")).resolve()
DB = HOME / "db.json"


def run(cmd, check=True):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if check and p.returncode:
        sys.exit(f"[radar] команда упала: {' '.join(map(str, cmd[:4]))} ...\n{p.stderr[-1500:]}")
    return p


def need(tool):
    if not shutil.which(tool):
        sys.exit(f"[radar] нет {tool}. Поставь: pip install yt-dlp faster-whisper instaloader; ffmpeg через winget/brew/apt")


def ytdlp(*args, check=True):
    need("yt-dlp")
    cmd = ["yt-dlp", "--no-warnings", "--ignore-config"]
    if shutil.which("node"):
        cmd += ["--js-runtimes", "node"]
    if os.environ.get("RADAR_COOKIES"):
        cmd += ["--cookies-from-browser", os.environ["RADAR_COOKIES"]]
    return run(cmd + list(args), check)


def load_db():
    db = json.loads(DB.read_text("utf-8")) if DB.exists() else {"videos": {}}
    db.setdefault("accounts", {})
    return db


def save_db(db):
    HOME.mkdir(parents=True, exist_ok=True)
    DB.write_text(json.dumps(db, ensure_ascii=False, indent=1), "utf-8")


def platform(url):
    u = url.lower()
    return "instagram" if "instagram.com" in u else "youtube" if "youtu" in u else "tiktok" if "tiktok" in u else "other"


def row(info, url=None):
    """Одна запись базы из метаданных yt-dlp."""
    d = info.get("upload_date") or ""
    if not d and info.get("timestamp"):
        d = dt.datetime.fromtimestamp(info["timestamp"], dt.timezone.utc).strftime("%Y%m%d")
    link = info.get("webpage_url") or info.get("url") or url or ""
    return {
        "id": str(info.get("id")), "url": link, "platform": platform(link),
        "account": (info.get("channel") if platform(link) == "instagram" else None) or info.get("uploader_id")
                   or info.get("channel") or info.get("uploader") or "",
        "title": (info.get("title") or info.get("description") or "")[:200],
        "caption": (info.get("description") or "")[:1500],
        "date": f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 else "",
        "duration": info.get("duration") or 0,
        "views": info.get("view_count") or 0, "likes": info.get("like_count") or 0,
        "comments": info.get("comment_count") or 0,
        "followers": info.get("channel_follower_count") or 0,
    }


def rescore(db):
    """Выброс = просмотры ролика / медиана просмотров аккаунта. ER = (лайки+комменты)/просмотры."""
    by = {}
    for v in db["videos"].values():
        by.setdefault(v["account"], []).append(v["views"])
    for v in db["videos"].values():
        med = statistics.median([x for x in by[v["account"]] if x] or [0])
        v["outlier"] = v["server_outlier"] if v.get("server_outlier") is not None else (round(v["views"] / med, 2) if med else 0)
        v["er"] = round((v["likes"] + v["comments"]) / v["views"] * 100, 2) if v["views"] else 0
    for name, vs in by.items():  # сводка по аккаунту для таблицы конкурентов
        if not name:
            continue
        mine = [v for v in db["videos"].values() if v["account"] == name]
        acc = db.setdefault("accounts", {}).setdefault(name, {"username": name})
        if acc.get("server"):  # цифры сервера посчитаны по полной ленте, локальные их не перетирают
            acc["posts"] = len(mine)
            continue
        dates = sorted(v["date"] for v in mine if v.get("date"))
        weeks = 1
        if len(dates) > 1:
            weeks = max(1, (dt.date.fromisoformat(dates[-1]) - dt.date.fromisoformat(dates[0])).days / 7)
        acc.update(posts=len(mine), median_views=int(statistics.median([x for x in vs if x] or [0])),
                   avg_er=round(statistics.mean([v["er"] for v in mine if v["er"]] or [0]), 2),
                   outliers=sum(1 for v in mine if v.get("outlier", 0) >= 3), per_week=round(len(dates) / weeks, 1),
                   platform=mine[0]["platform"], followers=acc.get("followers") or max(v.get("followers") or 0 for v in mine))


def upsert(db, r):
    old = db["videos"].get(r["id"], {})
    keep = {k: old[k] for k in ("watched", "dir", "transcript", "notes") if k in old}
    db["videos"][r["id"]] = {**old, **{k: v for k, v in r.items() if v or k not in old}, **keep}


# ---------- watch: один ролик глазами и ушами ----------

def probe(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]).stdout
    return float(out.strip() or 0)


def sheets(video, out, dur, n):
    """Раскадровки 4x3 с таймкодом в углу + отдельный лист первых 3 секунд (хук)."""
    stamp = "drawtext=text='%{pts\\:hms}':x=6:y=6:fontsize=20:fontcolor=white:box=1:boxcolor=black@0.6,"
    jobs = [("hook_%02d.jpg", f"fps=2,scale=360:-2,{{s}}tile=3x2", ["-t", "3"]),
            ("sheet_%02d.jpg", f"fps={n}/{max(dur, 1):.3f},scale=360:-2,{{s}}tile=4x3", [])]
    for name, vf, pre in jobs:
        for s in (stamp, ""):  # если в ffmpeg нет шрифтов, рисуем без таймкода
            p = run(["ffmpeg", "-y", "-v", "error", *pre, "-i", str(video), "-vf", vf.format(s=s),
                     "-q:v", "4", str(out / name)], check=False)
            if p.returncode == 0:
                break
    # Крупные кадры для чтения текста и шрифтов: первые 3 секунды и финал (призыв к действию).
    run(["ffmpeg", "-y", "-v", "error", "-t", "3", "-i", str(video), "-vf", f"fps=1,scale=720:-2,{stamp}null".replace(",null", ""),
         "-q:v", "3", str(out / "big_start_%02d.jpg")], check=False)
    run(["ffmpeg", "-y", "-v", "error", "-sseof", "-2.5", "-i", str(video), "-vf", "fps=1,scale=720:-2",
         "-q:v", "3", str(out / "big_end_%02d.jpg")], check=False)
    # Склейки: кадр на каждую смену плана. Даёт число склеек и ловит быстрые титры между точками выборки.
    p = run(["ffmpeg", "-y", "-v", "info", "-i", str(video), "-vf", f"select='gt(scene,0.28)',showinfo,scale=360:-2,{stamp}tile=4x3",
             "-vsync", "vfr", "-q:v", "4", str(out / "cuts_%02d.jpg")], check=False)
    times = [float(t) for t in re.findall(r"pts_time:([0-9.]+)", p.stderr)]
    (out / "cuts.json").write_text(json.dumps({"cuts": len(times), "times": [round(t, 2) for t in times],
                                               "avg_shot_sec": round(dur / (len(times) + 1), 2)}), "utf-8")
    return sorted(x.name for x in out.glob("*.jpg"))


def storyboard(info, out, n):
    """Облачный режим: видео-хост закрыт, берём готовые раскадровки YouTube (мелкие, но бесплатные)."""
    sbs = [f for f in info.get("formats", []) if str(f.get("format_id", "")).startswith("sb") and f.get("fragments")]
    if not sbs:
        return [], 0
    sb = max(sbs, key=lambda f: f.get("width") or 0)
    frags, per = sb["fragments"], (sb.get("rows") or 1) * (sb.get("columns") or 1)
    step = max(1, -(-len(frags) // max(12, n // per)))  # не больше ~12 листов на ролик
    names, t, lines = [], 0.0, []
    for i, fr in enumerate(frags):
        if i % step == 0:
            name = f"sheet_{len(names) + 1:02d}.jpg"
            try:
                req = urllib.request.Request(fr["url"], headers={"User-Agent": "Mozilla/5.0"})
                (out / name).write_bytes(urllib.request.urlopen(req, timeout=30).read())
                names.append(name)
                lines.append(f"{name}: с {int(t // 60):02d}:{int(t % 60):02d}, сетка {sb.get('columns')}x{sb.get('rows')}, слева направо и сверху вниз")
            except Exception as e:
                lines.append(f"{name}: не скачался ({e})")
        t += fr.get("duration") or 0
    sec = round(1 / sb["fps"], 1) if sb.get("fps") else 0
    (out / "frames.txt").write_text(f"Кадр каждые {sec} сек, размер кадра {sb.get('width')}x{sb.get('height')}\n" + "\n".join(lines), "utf-8")
    return names, sec


def clean_vtt(text):
    lines, last = [], None
    for ln in text.splitlines():
        if "-->" in ln or not ln.strip() or ln.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")) or ln.strip().isdigit():
            continue
        ln = re.sub(r"<[^>]+>", "", ln).strip()
        if ln and ln != last:
            lines.append(ln)
            last = ln
    return "\n".join(lines)


def transcript(url, video, out, lang, is_url, model_name=None):
    """Сначала бесплатные субтитры площадки, потом локальный Whisper."""
    if is_url:
        ytdlp("--skip-download", "--write-subs", "--write-auto-subs", "--sub-langs", "all,-live_chat" if lang == "auto" else f"{lang},{lang}-orig,en",
              "--sub-format", "vtt", "-o", str(out / "subs"), url, check=False)
        for f in sorted(out.glob("subs*.vtt")):
            t = clean_vtt(f.read_text("utf-8", "ignore"))
            if len(t) > 20:
                return t, "субтитры площадки"
    if not video:
        return "", "субтитров нет, а звук без видео-хоста не достать"
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return "", "нет faster-whisper (pip install faster-whisper)"
    # Каракалпакского в Whisper нет: слушаем как казахский (ближайший), результат черновой.
    wl = {"kaa": "kk", "auto": None}.get(lang, lang)
    hard = lang in ("uz", "kaa", "kk", "ky", "tg", "tk", "az")  # для этих языков малая модель ошибается, берём среднюю
    name, err = model_name or os.environ.get("RADAR_WHISPER_MODEL") or ("medium" if hard else "small"), ""
    for dev, ct in (("auto", "auto"), ("cpu", "int8")):  # видеокарта, потом процессор
        try:
            model = WhisperModel(name, device=dev, compute_type=ct)
            import numpy as np  # звук достаём ffmpeg-ом: не зависим от версии PyAV
            raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                                 capture_output=True).stdout
            if not raw:
                return "", "в ролике нет звуковой дорожки"
            segs, info = model.transcribe(np.frombuffer(raw, np.float32), language=wl, vad_filter=True)
            text = "\n".join(f"[{int(s.start // 60):02d}:{int(s.start % 60):02d}] {s.text.strip()}" for s in segs)
            note = ", каракалпакский распознан как казахский, сверять с текстом на экране" if lang == "kaa" else ""
            return text, f"whisper {name}, язык {info.language} ({round(info.language_probability * 100)}%){note}"
        except Exception as e:
            err = str(e)[:200]
    return "", f"whisper не завёлся: {err}"


def cmd_watch(a):
    need("ffmpeg")
    src, is_url = a.target, re.match(r"https?://", a.target) is not None
    info = {}
    if is_url and a.src:  # прямой файл из официального API: площадку не трогаем, цифры берём из базы
        code = src.rstrip("/").split("/")[-1]
        r = dict(load_db()["videos"].get(code) or {"id": code, "url": src, "platform": platform(src), "account": "",
                 "title": "", "caption": "", "date": "", "duration": 0, "views": 0, "likes": 0, "comments": 0, "followers": 0})
    elif is_url:
        info = json.loads(ytdlp("-J", "--no-playlist", src).stdout)
        r = row(info, src)
    else:
        r = {"id": Path(src).stem, "url": src, "platform": "file", "account": "local", "title": Path(src).name,
             "caption": "", "date": "", "duration": 0, "views": 0, "likes": 0, "comments": 0, "followers": 0}
    out = HOME / "watch" / re.sub(r"[^\w.-]", "_", r["id"])
    out.mkdir(parents=True, exist_ok=True)
    video, mode, step = Path(src), "видео", 0
    if is_url and a.src:
        req = urllib.request.Request(a.src, headers={"User-Agent": "Mozilla/5.0"})
        (out / "video.mp4").write_bytes(urllib.request.urlopen(req, timeout=120).read())
        video = out / "video.mp4"
    elif is_url:
        p = ytdlp("-f", "bv*[height<=720]+ba/b[height<=720]/b", "--merge-output-format", "mp4", "--no-playlist",
                  "-o", str(out / "video.%(ext)s"), src, check=False)
        got = [x for x in out.glob("video.*") if x.suffix != ".part"]
        video = got[0] if p.returncode == 0 and got else None
    if video:
        dur = probe(video)
        r["duration"] = r["duration"] or round(dur)
        frames, step = sheets(video, out, dur, a.frames), round(dur / a.frames, 1)
    else:
        mode = "раскадровка площадки (видео-хост закрыт или ролик не отдался)"
        frames, step = storyboard(info, out, a.frames)
    text, how = ("", "выключено") if a.no_audio else transcript(src, video, out, a.lang, is_url and not a.src, a.model)
    (out / "transcript.txt").write_text(text, "utf-8")
    r.update(watched=True, dir=str(out), transcript=text[:6000])
    cj = out / "cuts.json"
    if cj.exists():
        c = json.loads(cj.read_text("utf-8")); r.update(cuts=c["cuts"], avg_shot_sec=c["avg_shot_sec"])
    words = len(re.findall(r"[^\W\d_]+", re.sub(r"\[\d\d:\d\d\]", "", text)))
    if words and r.get("duration"):
        r["words_per_min"] = round(words / r["duration"] * 60)
    (out / "meta.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), "utf-8")
    db = load_db(); upsert(db, r); rescore(db); save_db(db)
    if is_url and video and not a.keep:
        video.unlink(missing_ok=True)
    print(json.dumps({"папка": str(out), "режим": mode, "кадры": frames, "шаг_кадров_сек": step,
                      "транскрипт": how, "символов": len(text), "склеек": r.get("cuts"), "средний_план_сек": r.get("avg_shot_sec"),
                      "слов_в_минуту": r.get("words_per_min"),
                      "мета": {k: r[k] for k in ("account", "title", "date", "duration", "views", "likes", "comments")}},
                     ensure_ascii=False, indent=1))
    print("\nДальше: открой Read-ом все jpg из папки (и frames.txt, если есть), прочитай transcript.txt.")


# ---------- scan: лента аккаунта с цифрами ----------

def scan_instagram(target, limit):
    try:
        import instaloader
    except ImportError:
        sys.exit("[radar] для ленты Instagram нужен instaloader: pip install instaloader")
    nick = re.sub(r"^@", "", target.rstrip("/").split("instagram.com/")[-1].split("/")[0].split("?")[0])
    L = instaloader.Instaloader(quiet=True, download_pictures=False, download_videos=False)
    if os.environ.get("RADAR_IG_USER"):  # сессия создаётся один раз: instaloader --login НИК
        L.load_session_from_file(os.environ["RADAR_IG_USER"])
    prof = instaloader.Profile.from_username(L.context, nick)
    rows = []
    for i, p in enumerate(prof.get_posts()):
        if i >= limit:
            break
        rows.append({"id": p.shortcode, "url": f"https://www.instagram.com/p/{p.shortcode}/", "platform": "instagram",
                     "account": nick, "title": (p.caption or "")[:200], "caption": (p.caption or "")[:1500],
                     "date": p.date_utc.strftime("%Y-%m-%d"), "duration": round(p.video_duration or 0) if p.is_video else 0,
                     "views": (p.video_play_count or p.video_view_count or 0) if p.is_video else 0,
                     "likes": p.likes, "comments": p.comments, "followers": prof.followers,
                     "kind": "video" if p.is_video else p.typename.replace("Graph", "").lower()})
    return rows


def cmd_scan(a):
    t = a.target
    if "instagram.com" in t or t.startswith("@"):
        rows = scan_instagram(t, a.limit)
    else:
        if re.search(r"youtube\.com/(@|channel/|c/)[^/]+/?$", t):
            t = t.rstrip("/") + ("/shorts" if a.shorts else "/videos")
        # По умолчанию один лёгкий запрос на весь канал: без дат и лайков, зато площадка не банит.
        flags = ["-J", "--playlist-end", str(a.limit), "--ignore-errors"] + ([] if a.full else ["--flat-playlist"])
        data = json.loads(ytdlp(*flags, t, check=False).stdout or "{}") or {}
        rows = [row(e, t) for e in (data.get("entries") or []) if e]
        if not rows:
            sys.exit("[radar] площадка ничего не отдала (проверка на бота или закрытый хост). Повтори позже или запусти дома.")
        for r in rows:
            r["account"] = r["account"] or data.get("uploader_id") or data.get("channel") or ""
        for r in rows:
            r["followers"] = r["followers"] or data.get("channel_follower_count") or 0
    db = load_db()
    for r in rows:
        upsert(db, r)
    rescore(db); save_db(db)
    acc = rows[0]["account"] if rows else "?"
    mine = sorted((v for v in db["videos"].values() if v["account"] == acc), key=lambda v: -v.get("outlier", 0))
    print(f"[radar] {acc}: в базе {len(mine)} публикаций. Топ по выбросу (просмотры / медиана аккаунта):")
    for v in mine[:10]:
        print(f"  x{v['outlier']:<6} {v['views']:>9} просм  ER {v['er']:>5}%  {v['date']}  {v['url']}  {v['title'][:60]}")


def ingest_server(d):
    """Ответы серверных инструментов radar_sync, radar_list, radar_top: кладём в локальную базу для выгрузки."""
    db = load_db()
    accs = d.get("accounts", []) if isinstance(d, dict) else [x for x in d if "code" not in x]
    posts = [] if isinstance(d, dict) else [x for x in d if "code" in x]
    for acc in accs:
        u = acc["username"]
        db["accounts"].setdefault(u, {"username": u}).update({k: v for k, v in acc.items() if k != "top" and v not in (None, "")})
        db["accounts"][u]["server"] = True
        db["accounts"][u].setdefault("url", f"https://www.instagram.com/{u}/")
        posts += [{**t, "username": u} for t in acc.get("top", [])]
    for x in posts:
        typ = x.get("type", "")
        upsert(db, {"id": x["code"], "url": f"https://www.instagram.com/{'reel' if typ == 'reels' else 'p'}/{x['code']}/", "platform": "instagram",
                    "account": x.get("username", ""), "title": x.get("caption", ""), "caption": x.get("caption", ""),
                    "date": str(x.get("posted_at") or x.get("date") or "")[:10], "duration": x.get("duration") or 0, "views": x.get("views") or 0,
                    "likes": x.get("likes") or 0, "comments": x.get("comments") or 0, "followers": 0, "kind": typ,
                    "hook": x.get("hook") or "", "hook_type": x.get("hook_type") or "", "notes": x.get("analysis") or ""})
        if x.get("outlier") is not None:
            db["videos"][x["code"]]["server_outlier"] = x["outlier"]
    rescore(db); save_db(db)
    print(f"[radar] в базе: аккаунтов {len(db['accounts'])}, публикаций {len(db['videos'])}")


def cmd_ingest(a):
    """Лента Instagram из официального Graph API (business_discovery), сохранённая в json-файл."""
    d = json.loads(Path(a.file).read_text("utf-8"))
    if isinstance(d, list) or (isinstance(d, dict) and isinstance(d.get("accounts"), list)):
        return ingest_server(d)
    bd = d.get("business_discovery") or d
    rows = []
    for m in bd.get("items") or []:  # компактный формат инструмента ig_radar
        rows.append({"id": m["code"], "url": f"https://www.instagram.com/{'reel' if m.get('type') == 'reels' else 'p'}/{m['code']}/",
                     "platform": "instagram", "account": bd.get("username", ""), "title": m.get("caption", ""),
                     "caption": m.get("caption", ""), "date": m.get("date", ""), "duration": 0, "views": m.get("views") or 0,
                     "likes": m.get("likes") or 0, "comments": m.get("comments") or 0, "followers": bd.get("followers") or 0,
                     "kind": m.get("type", ""), "has_video": bool(m.get("has_video"))})
    bd.setdefault("followers_count", bd.get("followers"))
    if bd.get("username"):
        prof = {"username": bd["username"], "name": bd.get("name") or "", "bio": bd.get("bio") or bd.get("biography") or "",
                "website": bd.get("website") or "", "followers": bd.get("followers_count") or 0,
                "follows": bd.get("follows") or bd.get("follows_count") or 0, "url": f"https://www.instagram.com/{bd['username']}/"}
        dbp = load_db(); dbp["accounts"].setdefault(bd["username"], {}).update({k: v for k, v in prof.items() if v}); save_db(dbp)
    for m in (bd.get("media") or {}).get("data", []):
        code = m.get("permalink", "").rstrip("/").split("/")[-1] or m["id"]
        rows.append({"id": code, "url": m.get("permalink", ""), "platform": "instagram", "account": bd.get("username", ""),
                     "title": (m.get("caption") or "")[:200], "caption": (m.get("caption") or "")[:1500],
                     "date": (m.get("timestamp") or "")[:10], "duration": 0, "views": m.get("view_count") or 0,
                     "likes": m.get("like_count") or 0, "comments": m.get("comments_count") or 0,
                     "shares": m.get("shares") or 0, "saves": m.get("saved") or 0, "reach": m.get("reach") or 0,
                     "followers": bd.get("followers_count") or 0,
                     "kind": (m.get("media_product_type") or m.get("media_type") or "").lower()})
    db = load_db()
    for r in rows:
        upsert(db, r)
    rescore(db); save_db(db)
    top = sorted((v for v in db["videos"].values() if v["account"] == bd.get("username")), key=lambda v: -v.get("outlier", 0))
    print(f"[radar] {bd.get('username')}: подписчиков {bd.get('followers_count')}, в базе {len(top)} публикаций. Топ по выбросу:")
    for v in top[:10]:
        print(f"  x{v['outlier']:<6} {v['views']:>9} просм  {v['likes']:>7} лайк  {v['date']}  {v['url']}  {v['title'][:50]}")


def cmd_pics(a):
    """Скачивает картинки по ссылкам (аватар, обложки, слайды каруселей) и клеит в листы 4x3 для просмотра."""
    need("ffmpeg")
    out = HOME / "pics" / re.sub(r"[^\w.-]", "_", a.name)
    out.mkdir(parents=True, exist_ok=True)
    urls = list(a.urls)
    if a.file:  # json: {"подпись": "ссылка" | ["ссылки"]} или просто список ссылок
        d = json.loads(Path(a.file).read_text("utf-8"))
        for k, v in (d.items() if isinstance(d, dict) else enumerate(d)):
            urls += v if isinstance(v, list) else [v]
    got = []
    for i, u in enumerate(urls, 1):
        f = out / f"p{i:03d}.jpg"
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            f.write_bytes(urllib.request.urlopen(req, timeout=60).read())
            got.append(f)
        except Exception as e:
            print(f"[radar] не скачалось {i}: {str(e)[:80]}")
    for n in range(0, len(got), 12):
        part = got[n:n + 12]
        ins = [x for f in part for x in ("-i", str(f))]
        norm = "".join(f"[{i}:v]scale=360:450:force_original_aspect_ratio=decrease,pad=360:450:(ow-iw)/2:(oh-ih)/2[v{i}];" for i in range(len(part)))
        cols = min(4, len(part)); rows = -(-len(part) // cols)
        lay = "|".join(f"{(i % cols) * 360}_{(i // cols) * 450}" for i in range(len(part)))
        graph = norm + "".join(f"[v{i}]" for i in range(len(part))) + f"xstack=inputs={len(part)}:layout={lay}:fill=black[o]" if len(part) > 1 else norm.replace("[v0];", "[o]")
        run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", graph, "-map", "[o]", "-q:v", "4", str(out / f"sheet_{n // 12 + 1:02d}.jpg")], check=False)
    print(json.dumps({"папка": str(out), "скачано": len(got), "листы": sorted(x.name for x in out.glob("sheet_*.jpg")),
                      "порядок": "слева направо, сверху вниз, в порядке переданных ссылок"}, ensure_ascii=False, indent=1))


def cmd_tag(a):
    """Метки аккаунта для фильтров: ниша, гео, язык, пол и возраст автора или аудитории, заметка."""
    db = load_db()
    acc = db["accounts"].setdefault(a.username.lstrip("@"), {"username": a.username.lstrip("@")})
    for k in ("niche", "geo", "lang", "gender", "age", "kind", "note"):
        if getattr(a, k):
            acc[k] = getattr(a, k)
    rescore(db); save_db(db)
    print(json.dumps(acc, ensure_ascii=False))


ACC_COLS = [("username", "Аккаунт"), ("name", "Имя"), ("niche", "Ниша"), ("geo", "Гео"), ("lang", "Язык"), ("gender", "Пол"),
            ("age", "Возраст"), ("kind", "Тип"), ("followers", "Подписчики"), ("median_views", "Медиана просмотров"),
            ("avg_er", "ER %"), ("outliers", "Выбросов от x3"), ("per_week", "Публикаций в неделю"), ("posts", "В базе"),
            ("url", "Ссылка"), ("bio", "Био"), ("note", "Заметка")]
HOOK_COLS = [("account", "Аккаунт"), ("hook", "Хук дословно"), ("hook_type", "Тип хука"), ("views", "Просмотры"), ("outlier", "Выброс x"),
             ("date", "Дата"), ("url", "Ссылка")]
VID_COLS = [("account", "Аккаунт"), ("platform", "Площадка"), ("date", "Дата"), ("kind", "Формат"), ("views", "Просмотры"),
            ("outlier", "Выброс x"), ("er", "ER %"), ("likes", "Лайки"), ("comments", "Комментарии"), ("duration", "Сек"),
            ("cuts", "Склеек"), ("words_per_min", "Слов в минуту"), ("hook", "Хук"), ("hook_type", "Тип хука"),
            ("url", "Ссылка"), ("title", "Подпись"), ("notes", "Разбор"), ("transcript", "Транскрипт")]


def cmd_export(a):
    """Выгрузка базы: xlsx, csv, pdf, md, json. --report файл.md добавляет в PDF и md текст разбора."""
    db = load_db(); rescore(db)
    pick = set(x.lstrip("@") for x in a.accounts) if a.accounts else None
    accs = sorted((x for x in db["accounts"].values() if not pick or x.get("username") in pick), key=lambda x: -(x.get("median_views") or 0))
    vids = sorted((v for v in db["videos"].values() if not pick or v["account"] in pick), key=lambda v: -(v.get("outlier") or 0))
    hot = [v for v in vids if (v.get("outlier") or 0) >= 3]
    report = Path(a.report).read_text("utf-8") if a.report else ""
    out = HOME / "export"; out.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%d")
    base = out / f"radar_{a.name or stamp}"
    rows = lambda items, cols: [[("" if x.get(k) is None else x.get(k)) for k, _ in cols] for x in items]
    done, fmts = [], ["xlsx", "csv", "pdf", "md", "json"] if a.format == "all" else a.format.split(",")
    if "json" in fmts:
        base.with_suffix(".json").write_text(json.dumps({"accounts": accs, "videos": vids}, ensure_ascii=False, indent=1), "utf-8")
        done.append(base.with_suffix(".json"))
    if "csv" in fmts:
        import csv
        for tag, items, cols in (("accounts", accs, ACC_COLS), ("posts", vids, VID_COLS)):
            f = Path(f"{base}_{tag}.csv")
            with f.open("w", newline="", encoding="utf-8-sig") as fh:  # BOM, чтобы Excel открыл кириллицу
                w = csv.writer(fh, delimiter=";"); w.writerow([t for _, t in cols]); w.writerows(rows(items, cols))
            done.append(f)
    if "xlsx" in fmts:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        wb = Workbook(); wb.remove(wb.active)
        for title, items, cols in (("Аккаунты", accs, ACC_COLS), ("Залетевшие", hot, VID_COLS),
                                   ("Хуки", [v for v in vids if v.get("hook")], HOOK_COLS), ("Все публикации", vids, VID_COLS)):
            ws = wb.create_sheet(title); ws.append([t for _, t in cols])
            for r in rows(items, cols):
                ws.append([str(c)[:32000] if isinstance(c, str) else c for c in r])
            for c in ws[1]:
                c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="C2410C")
                c.alignment = Alignment(vertical="center", wrap_text=True)
            for i, (k, _) in enumerate(cols, 1):
                ws.column_dimensions[ws.cell(1, i).column_letter].width = 50 if k in ("bio", "title", "notes", "transcript", "note") else 34 if k == "url" else 16
            ws.freeze_panes = "B2"; ws.auto_filter.ref = ws.dimensions
        if report:
            ws = wb.create_sheet("Разбор", 0); ws.column_dimensions["A"].width = 120
            for ln in report.splitlines():
                ws.append([ln]); ws.cell(ws.max_row, 1).alignment = Alignment(wrap_text=True, vertical="top")
        wb.save(base.with_suffix(".xlsx")); done.append(base.with_suffix(".xlsx"))
    md = [f"# Радар конкурентов, {stamp}", ""]
    if report:
        md += [report, ""]
    md += ["## Аккаунты", "", "| Аккаунт | Ниша | Гео | Язык | Подписчики | Медиана просм. | ER % | Выбросов | В неделю |", "|---|---|---|---|---|---|---|---|---|"]
    md += [f"| {x.get('username','')} | {x.get('niche','')} | {x.get('geo','')} | {x.get('lang','')} | {x.get('followers',0)} | {x.get('median_views',0)} | {x.get('avg_er',0)} | {x.get('outliers',0)} | {x.get('per_week','')} |" for x in accs]
    md += ["", "## Залетевшие (выброс от x3)", "", "| Аккаунт | Дата | Просмотры | Выброс | ER % | Ссылка |", "|---|---|---|---|---|---|"]
    md += [f"| {v['account']} | {v.get('date','')} | {v.get('views',0)} | x{v.get('outlier',0)} | {v.get('er',0)} | {v.get('url','')} |" for v in hot[:50]]
    if "md" in fmts:
        base.with_suffix(".md").write_text("\n".join(md), "utf-8"); done.append(base.with_suffix(".md"))
    if "pdf" in fmts:
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib.styles import ParagraphStyle
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from xml.sax.saxutils import escape
            font = next((f for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/Library/Fonts/Arial Unicode.ttf",
                                     "C:/Windows/Fonts/arial.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf") if Path(f).exists()), None)
            if not font:
                raise RuntimeError("нет шрифта с кириллицей")
            pdfmetrics.registerFont(TTFont("R", font))
            bold = font.replace("DejaVuSans.ttf", "DejaVuSans-Bold.ttf").replace("arial.ttf", "arialbd.ttf")
            pdfmetrics.registerFont(TTFont("RB", bold if Path(bold).exists() else font))
            P = ParagraphStyle("p", fontName="R", fontSize=9, leading=12.5)
            H = ParagraphStyle("h", fontName="RB", fontSize=14, leading=18, spaceBefore=10, spaceAfter=6)
            T = ParagraphStyle("t", fontName="R", fontSize=7.5, leading=9.5)
            def table(head, data, widths):
                t = Table([[Paragraph(f"<b>{escape(str(h))}</b>", T) for h in head]] + [[Paragraph(escape(str(c))[:300], T) for c in r] for r in data],
                          colWidths=widths, repeatRows=1)
                t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3d9cc")), ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                                       ("VALIGN", (0, 0), (-1, -1), "TOP")]))
                return t
            flow = [Paragraph(f"Радар конкурентов, {stamp}", ParagraphStyle("tt", fontName="RB", fontSize=18, leading=22)), Spacer(1, 8)]
            for ln in report.splitlines():
                if ln.startswith("#"):
                    flow.append(Paragraph(escape(ln.lstrip("# ")), H))
                elif ln.strip():
                    flow.append(Paragraph(re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escape(ln)), P))
                else:
                    flow.append(Spacer(1, 4))
            flow.append(Paragraph("Аккаунты", H))
            flow.append(table(["Аккаунт", "Ниша", "Гео", "Язык", "Подписчики", "Медиана", "ER %", "Выбросов", "В нед."],
                              [[x.get("username", ""), x.get("niche", ""), x.get("geo", ""), x.get("lang", ""), x.get("followers", 0), x.get("median_views", 0),
                                x.get("avg_er", 0), x.get("outliers", 0), x.get("per_week", "")] for x in accs], [110, 90, 80, 45, 70, 70, 45, 55, 45]))
            flow.append(Paragraph("Залетевшие ролики (выброс от x3)", H))
            flow.append(table(["Аккаунт", "Дата", "Просмотры", "Выброс", "ER %", "Подпись", "Ссылка"],
                              [[v["account"], v.get("date", ""), v.get("views", 0), f"x{v.get('outlier', 0)}", v.get("er", 0), v.get("title", "")[:120], v.get("url", "")]
                               for v in hot[:60]], [90, 55, 65, 45, 40, 260, 210]))
            SimpleDocTemplate(str(base.with_suffix(".pdf")), pagesize=landscape(A4), leftMargin=28, rightMargin=28, topMargin=28, bottomMargin=28).build(flow)
            done.append(base.with_suffix(".pdf"))
        except Exception as e:
            print(f"[radar] PDF не собрался: {e}. Поставь: pip install reportlab")
    print(json.dumps({"аккаунтов": len(accs), "публикаций": len(vids), "залетевших": len(hot), "файлы": [str(f) for f in done]}, ensure_ascii=False, indent=1))


# ---------- dash: один html-файл с фильтрами ----------

PAGE = """<!doctype html><html lang=ru><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Радар конкурентов</title><style>
:root{--bg:#f6f5f1;--card:#fff;--ink:#1c1b19;--mut:#77736b;--line:#e3e0d8;--acc:#c2410c}
@media(prefers-color-scheme:dark){:root{--bg:#141413;--card:#1f1e1c;--ink:#eeebe4;--mut:#99948a;--line:#33312d;--acc:#fb923c}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,sans-serif;padding:16px}
h1{font-size:22px;margin:0 0 4px}.sub{color:var(--mut);margin-bottom:14px}
.bar{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px}
input,select{background:var(--card);color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:8px 10px;font:inherit;min-width:0}
input[type=search]{flex:1 1 220px}.kpi{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:8px;margin-bottom:14px}
.kpi div{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px}.kpi b{display:block;font-size:20px}
.kpi span{color:var(--mut);font-size:12px}.wrap{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:10px}
table{border-collapse:collapse;width:100%;min-width:760px}th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{font-size:12px;color:var(--mut);cursor:pointer;white-space:nowrap;user-select:none}td.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
a{color:var(--acc);text-decoration:none}.hot{color:var(--acc);font-weight:700}.tag{font-size:11px;color:var(--mut)}
details{margin-top:4px;color:var(--mut);font-size:13px;white-space:pre-wrap}</style>
<h1>Радар конкурентов</h1><div class=sub id=sub></div>
<h2 style="font-size:17px;margin:14px 0 8px">Аккаунты</h2>
<div class=bar><input type=search id=aq placeholder="Поиск по нику, имени, био, заметке">
<select id=an></select><select id=ag></select><select id=al></select><select id=ax></select><select id=aa></select>
<select id=af><option value="0-0">Любой размер<option value="0-10000">до 10 тыс.<option value="10000-100000">10-100 тыс.<option value="100000-1000000">100 тыс.-1 млн<option value="1000000-0">от 1 млн</select></div>
<div class=wrap style="margin-bottom:18px"><table><thead><tr><th data-a=username>Аккаунт</th><th data-a=niche>Ниша</th><th data-a=geo>Гео</th><th data-a=lang>Язык</th>
<th data-a=gender>Пол</th><th data-a=age>Возраст</th><th data-a=followers>Подписчики</th><th data-a=median_views>Медиана просм.</th>
<th data-a=avg_er>ER %</th><th data-a=outliers>Выбросов</th><th data-a=per_week>В неделю</th></tr></thead><tbody id=atb></tbody></table></div>
<h2 style="font-size:17px;margin:14px 0 8px">Публикации</h2>
<div class=bar><input type=search id=q placeholder="Поиск по заголовку, подписи, транскрипту">
<select id=acc></select><select id=pf></select>
<select id=out><option value=0>Любой выброс<option value=1.5>от x1.5<option value=2>от x2<option value=3>от x3<option value=5>от x5</select>
<select id=w><option value="">Все<option value=1>Только просмотренные мной</select></div>
<div class=kpi id=kpi></div><div class=wrap><table><thead><tr>
<th data-k=date>Дата</th><th data-k=account>Аккаунт</th><th data-k=title>Ролик</th><th data-k=views>Просмотры</th>
<th data-k=outlier>Выброс</th><th data-k=er>ER %</th><th data-k=likes>Лайки</th><th data-k=comments>Комм.</th><th data-k=duration>Сек</th>
</tr></thead><tbody id=tb></tbody></table></div>
<script>const A=__ACC__;const D=__DATA__;let sk='outlier',dir=-1;const $=id=>document.getElementById(id),f=n=>(n||0).toLocaleString('ru');
const esc=s=>String(s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function opts(el,k,all){el.innerHTML='<option value="">'+all+[...new Set(D.map(v=>v[k]))].sort().map(x=>'<option>'+esc(x)).join('')}
opts($('acc'),'account','Все аккаунты');opts($('pf'),'platform','Все площадки');
function draw(){const q=$('q').value.toLowerCase(),a=$('acc').value,p=$('pf').value,o=+$('out').value,w=$('w').value;
let r=D.filter(v=>(!a||v.account==a)&&(!p||v.platform==p)&&(v.outlier||0)>=o&&(!w||v.watched)&&
(!q||(v.title+' '+v.caption+' '+(v.transcript||'')).toLowerCase().includes(q)));
r.sort((x,y)=>(x[sk]>y[sk]?1:x[sk]<y[sk]?-1:0)*dir);
const med=a=>{a=a.filter(Boolean).sort((x,y)=>x-y);return a.length?a[a.length>>1]:0};
$('kpi').innerHTML=[['Публикаций',f(r.length)],['Аккаунтов',new Set(r.map(v=>v.account)).size],['Медиана просмотров',f(med(r.map(v=>v.views)))],
['Медиана ER',med(r.map(v=>v.er))+'%'],['Выбросов от x3',r.filter(v=>v.outlier>=3).length]].map(k=>'<div><b>'+k[1]+'</b><span>'+k[0]+'</span></div>').join('');
$('tb').innerHTML=r.map(v=>'<tr><td>'+v.date+'</td><td>'+esc(v.account)+'<br><span class=tag>'+v.platform+'</span></td><td><a href="'+esc(v.url)+'" target=_blank rel=noopener>'+
esc(v.title||v.id)+'</a>'+(v.watched?' <span class=tag>👁 просмотрено</span>':'')+(v.transcript?'<details><summary>транскрипт</summary>'+esc(v.transcript)+'</details>':'')+
'</td><td class=n>'+f(v.views)+'</td><td class="n '+(v.outlier>=3?'hot':'')+'">x'+(v.outlier||0)+'</td><td class=n>'+(v.er||0)+'</td><td class=n>'+f(v.likes)+
'</td><td class=n>'+f(v.comments)+'</td><td class=n>'+(v.duration||'')+'</td></tr>').join('')}
document.querySelectorAll('th[data-k]').forEach(t=>t.onclick=()=>{dir=sk==t.dataset.k?-dir:-1;sk=t.dataset.k;draw()});
let ak='median_views',ad=-1;function aopts(id,k,all){$(id).innerHTML='<option value="">'+all+[...new Set(A.map(v=>v[k]).filter(Boolean))].sort().map(x=>'<option>'+esc(x)).join('')}
aopts('an','niche','Все ниши');aopts('ag','geo','Любое гео');aopts('al','lang','Любой язык');aopts('ax','gender','Любой пол');aopts('aa','age','Любой возраст');
function adraw(){const q=$('aq').value.toLowerCase(),[lo,hi]=$('af').value.split('-').map(Number),m={niche:$('an').value,geo:$('ag').value,lang:$('al').value,gender:$('ax').value,age:$('aa').value};
let r=A.filter(v=>Object.keys(m).every(k=>!m[k]||v[k]==m[k])&&(v.followers||0)>=lo&&(!hi||(v.followers||0)<hi)&&(!q||[v.username,v.name,v.bio,v.note].join(' ').toLowerCase().includes(q)));
r.sort((x,y)=>((x[ak]||0)>(y[ak]||0)?1:(x[ak]||0)<(y[ak]||0)?-1:0)*ad);
$('atb').innerHTML=r.map(v=>'<tr><td><a href="'+esc(v.url||'#')+'" target=_blank rel=noopener>'+esc(v.username)+'</a><br><span class=tag>'+esc(v.name||'')+'</span>'+(v.bio||v.note?'<details><summary>био и заметка</summary>'+esc(v.bio||'')+' | '+esc(v.note||'')+'</details>':'')+'</td><td>'+esc(v.niche||'')+'</td><td>'+esc(v.geo||'')+'</td><td>'+esc(v.lang||'')+'</td><td>'+esc(v.gender||'')+'</td><td>'+esc(v.age||'')+'</td><td class=n>'+f(v.followers)+'</td><td class=n>'+f(v.median_views)+'</td><td class=n>'+(v.avg_er||0)+'</td><td class="n '+(v.outliers?'hot':'')+'">'+(v.outliers||0)+'</td><td class=n>'+(v.per_week||'')+'</td></tr>').join('')}
document.querySelectorAll('th[data-a]').forEach(t=>t.onclick=()=>{ad=ak==t.dataset.a?-ad:-1;ak=t.dataset.a;adraw()});['aq','an','ag','al','ax','aa','af'].forEach(i=>$(i).oninput=adraw);adraw();
['q','acc','pf','out','w'].forEach(i=>$(i).oninput=draw);$('sub').textContent='Обновлено __WHEN__. Клик по заголовку столбца сортирует.';draw()</script>"""


def cmd_dash(a):
    db = load_db(); rescore(db)
    data = json.dumps(list(db["videos"].values()), ensure_ascii=False).replace("</", "<\\/")
    out = HOME / "dashboard.html"
    accs = json.dumps(list(db["accounts"].values()), ensure_ascii=False).replace("</", "<\\/")
    out.write_text(PAGE.replace("__ACC__", accs).replace("__DATA__", data).replace("__WHEN__", html.escape(dt.datetime.now().strftime("%d.%m.%Y %H:%M"))), "utf-8")
    print(f"[radar] {out} ({len(db['videos'])} публикаций)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("watch"); w.add_argument("target"); w.add_argument("--frames", type=int, default=24)
    w.add_argument("--lang", default="auto", help="auto, ru, uz, kaa, en или любой код Whisper")
    w.add_argument("--model", help="small, medium, large-v3 или путь к своей модели"); w.add_argument("--no-audio", action="store_true"); w.add_argument("--keep", action="store_true")
    w.add_argument("--src", help="прямая ссылка на mp4 (media_url из Graph API)")
    s = sub.add_parser("scan"); s.add_argument("target"); s.add_argument("--limit", type=int, default=30); s.add_argument("--shorts", action="store_true")
    s.add_argument("--full", action="store_true", help="запрос на каждый ролик: даты и лайки, но выше риск блокировки")
    g = sub.add_parser("ingest"); g.add_argument("file")
    pc = sub.add_parser("pics"); pc.add_argument("name"); pc.add_argument("urls", nargs="*"); pc.add_argument("--file")
    tg = sub.add_parser("tag"); tg.add_argument("username")
    for k in ("niche", "geo", "lang", "gender", "age", "kind", "note"):
        tg.add_argument("--" + k)
    ex = sub.add_parser("export"); ex.add_argument("--format", default="all", help="xlsx,csv,pdf,md,json или all")
    ex.add_argument("--accounts", nargs="*", default=[]); ex.add_argument("--report"); ex.add_argument("--name")
    sub.add_parser("dash")
    a = ap.parse_args()
    {"watch": cmd_watch, "scan": cmd_scan, "ingest": cmd_ingest, "pics": cmd_pics, "tag": cmd_tag, "export": cmd_export, "dash": cmd_dash}[a.cmd](a)


if __name__ == "__main__":
    main()
