#!/usr/bin/env python3
"""radar: глаза и уши для анализа конкурентов (YouTube, Instagram, любой сайт из yt-dlp).

  radar.py watch <url|файл> [--frames 24] [--lang ru] [--no-audio]
  radar.py scan  <url канала или @ник IG> [--limit 30]
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
    return json.loads(DB.read_text("utf-8")) if DB.exists() else {"videos": {}}


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
        "account": info.get("uploader_id") or info.get("channel") or info.get("uploader") or "",
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
        v["outlier"] = round(v["views"] / med, 2) if med else 0
        v["er"] = round((v["likes"] + v["comments"]) / v["views"] * 100, 2) if v["views"] else 0


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


def transcript(url, video, out, lang, is_url):
    """Сначала бесплатные субтитры площадки, потом локальный Whisper."""
    if is_url:
        ytdlp("--skip-download", "--write-subs", "--write-auto-subs", "--sub-langs", f"{lang},{lang}-orig,en",
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
    name, err = os.environ.get("RADAR_WHISPER_MODEL", "small"), ""
    for dev, ct in (("auto", "auto"), ("cpu", "int8")):  # видеокарта, потом процессор
        try:
            model = WhisperModel(name, device=dev, compute_type=ct)
            segs, info = model.transcribe(str(video), language=None if lang == "auto" else lang, vad_filter=True)
            text = "\n".join(f"[{int(s.start // 60):02d}:{int(s.start % 60):02d}] {s.text.strip()}" for s in segs)
            return text, f"whisper {name} ({info.language})"
        except Exception as e:
            err = str(e)[:200]
    return "", f"whisper не завёлся: {err}"


def cmd_watch(a):
    need("ffmpeg")
    src, is_url = a.target, re.match(r"https?://", a.target) is not None
    if is_url:
        info = json.loads(ytdlp("-J", "--no-playlist", src).stdout)
        r = row(info, src)
    else:
        r = {"id": Path(src).stem, "url": src, "platform": "file", "account": "local", "title": Path(src).name,
             "caption": "", "date": "", "duration": 0, "views": 0, "likes": 0, "comments": 0, "followers": 0}
    out = HOME / "watch" / re.sub(r"[^\w.-]", "_", r["id"])
    out.mkdir(parents=True, exist_ok=True)
    video, mode, step = Path(src), "видео", 0
    if is_url:
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
    text, how = ("", "выключено") if a.no_audio else transcript(src, video, out, a.lang, is_url)
    (out / "transcript.txt").write_text(text, "utf-8")
    r.update(watched=True, dir=str(out), transcript=text[:6000])
    (out / "meta.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), "utf-8")
    db = load_db(); upsert(db, r); rescore(db); save_db(db)
    if is_url and video and not a.keep:
        video.unlink(missing_ok=True)
    print(json.dumps({"папка": str(out), "режим": mode, "кадры": frames, "шаг_кадров_сек": step,
                      "транскрипт": how, "символов": len(text),
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
<div class=bar><input type=search id=q placeholder="Поиск по заголовку, подписи, транскрипту">
<select id=acc></select><select id=pf></select>
<select id=out><option value=0>Любой выброс<option value=1.5>от x1.5<option value=2>от x2<option value=3>от x3<option value=5>от x5</select>
<select id=w><option value="">Все<option value=1>Только просмотренные мной</select></div>
<div class=kpi id=kpi></div><div class=wrap><table><thead><tr>
<th data-k=date>Дата</th><th data-k=account>Аккаунт</th><th data-k=title>Ролик</th><th data-k=views>Просмотры</th>
<th data-k=outlier>Выброс</th><th data-k=er>ER %</th><th data-k=likes>Лайки</th><th data-k=comments>Комм.</th><th data-k=duration>Сек</th>
</tr></thead><tbody id=tb></tbody></table></div>
<script>const D=__DATA__;let sk='outlier',dir=-1;const $=id=>document.getElementById(id),f=n=>(n||0).toLocaleString('ru');
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
document.querySelectorAll('th').forEach(t=>t.onclick=()=>{dir=sk==t.dataset.k?-dir:-1;sk=t.dataset.k;draw()});
['q','acc','pf','out','w'].forEach(i=>$(i).oninput=draw);$('sub').textContent='Обновлено __WHEN__. Клик по заголовку столбца сортирует.';draw()</script>"""


def cmd_dash(a):
    db = load_db(); rescore(db)
    data = json.dumps(list(db["videos"].values()), ensure_ascii=False).replace("</", "<\\/")
    out = HOME / "dashboard.html"
    out.write_text(PAGE.replace("__DATA__", data).replace("__WHEN__", html.escape(dt.datetime.now().strftime("%d.%m.%Y %H:%M"))), "utf-8")
    print(f"[radar] {out} ({len(db['videos'])} публикаций)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("watch"); w.add_argument("target"); w.add_argument("--frames", type=int, default=24)
    w.add_argument("--lang", default="ru"); w.add_argument("--no-audio", action="store_true"); w.add_argument("--keep", action="store_true")
    s = sub.add_parser("scan"); s.add_argument("target"); s.add_argument("--limit", type=int, default=30); s.add_argument("--shorts", action="store_true")
    s.add_argument("--full", action="store_true", help="запрос на каждый ролик: даты и лайки, но выше риск блокировки")
    sub.add_parser("dash")
    a = ap.parse_args()
    {"watch": cmd_watch, "scan": cmd_scan, "dash": cmd_dash}[a.cmd](a)


if __name__ == "__main__":
    main()
