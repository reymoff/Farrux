#!/usr/bin/env python3
"""Мафия для нейросетей. Ведущий = этот скрипт, игроки = модели по OpenAI-совместимому API.
Запуск: python3 mafia.py config.json [seed]
"""
import json, os, random, re, sys, time, urllib.request, urllib.error
from collections import Counter

NAMES = ["Алиса", "Борис", "Вера", "Глеб", "Дина", "Егор", "Жанна", "Захар",
         "Инга", "Кирилл", "Лада", "Марк", "Нина", "Олег", "Полина", "Роман"]
ROLE_RU = {"mafia": "мафия", "doctor": "доктор", "commissar": "комиссар", "civilian": "мирный житель"}

RULES = """Ты играешь в настольную игру Мафия. Вокруг стола сидят игроки, все они нейросети разных компаний.
Правила:
- Роли: мафия (знает своих), доктор, комиссар, мирные жители. Роли скрыты.
- Ночь: мафия убивает одного игрока. Доктор лечит одного (если угадал жертву, она выживает; дважды подряд одного лечить нельзя). Комиссар проверяет одного и узнаёт, мафия он или нет.
- День: все обсуждают и голосуют. Набравший больше всех голосов выбывает. При равенстве не выбывает никто.
- Роль выбывшего вскрывается.
- Мирные (с доктором и комиссаром) побеждают, когда вся мафия выбыла. Мафия побеждает, когда её не меньше, чем остальных.
Играй на победу своей команды: анализируй речи и голосования, лови противоречия. Мафии можно и нужно врать и притворяться мирной.
Говори по-русски, живо и коротко, как человек за столом. Не раскрывай, какая ты нейросеть."""


class Player:
    def __init__(self, name, cfg):
        self.name, self.cfg = name, cfg
        self.label = cfg["label"]
        self.role = None
        self.alive = True
        self.private = []   # личные заметки: ночные действия, проверки
        self.fails = 0


def call_llm(cfg, system, user, max_tokens=1500):
    if cfg.get("gguf"):
        import local
        return local.chat(cfg, system + cfg.get("sys_suffix", ""), user, cfg.get("max_tokens", 500))
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    body = {"model": cfg["model"], "max_tokens": max_tokens, "temperature": cfg.get("temperature", 0.9),
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    body.update(cfg.get("extra", {}))
    key = os.environ.get(cfg.get("key_env", ""), "") or cfg.get("key", "dummy")
    headers = {"Content-Type": "application/json", "Authorization": "Bearer " + key,
               "User-Agent": "mafia-bench/1.0"}
    last = ""
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, json.dumps(body).encode(), headers)
            with urllib.request.urlopen(req, timeout=180) as r:
                d = json.loads(r.read())
            txt = d["choices"][0]["message"].get("content") or ""
            if txt.strip():
                return txt
            last = "пустой ответ"
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.read()[:200].decode('utf-8', 'ignore')}"
            if e.code in (400, 401, 403, 404):
                break
        except Exception as e:
            last = repr(e)[:200]
        time.sleep(cfg.get("retry_sleep", 8) * (attempt + 1))
    raise RuntimeError(last)


def parse_json(txt):
    txt = re.sub(r"<think>.*?</think>", "", txt, flags=re.S)
    m = re.search(r"\{.*\}", txt, flags=re.S)
    if m:
        try:
            d = json.loads(m.group(0))
            if isinstance(d, dict):
                return d
        except Exception:
            pass
    # JSON оборван или кривой: вытаскиваем поля по одному
    d = {}
    for k in ("thoughts", "speech", "message", "target"):
        m = re.search(r'"%s"\s*:\s*"((?:[^"\\]|\\.)*)' % k, txt, flags=re.S)
        if m:
            d[k] = m.group(1).replace('\\"', '"').replace("\\n", " ").strip()
    return d


class Game:
    def __init__(self, config, seed=None):
        self.rng = random.Random(seed)
        cfgs = config["players"]
        names = NAMES[:len(cfgs)]
        self.rng.shuffle(names)
        self.players = [Player(n, c) for n, c in zip(names, cfgs)]
        n = len(self.players)
        n_mafia = config.get("mafia") or max(1, round(n / 4))
        roles = ["mafia"] * n_mafia + ["doctor", "commissar"]
        roles += ["civilian"] * (n - len(roles))
        self.rng.shuffle(roles)
        for p, r in zip(self.players, roles):
            p.role = r
        self.delay = config.get("delay", 0)
        self.out = config.get("out")
        self.public = []     # то, что слышат все
        self.events = []     # полный протокол для повтора
        self.day = 0
        self.last_heal = None
        self.winner = None
        self.ev("setup", players=[{"name": p.name, "label": p.label, "role": p.role} for p in self.players])

    # ---------- утилиты
    def ev(self, kind, **kw):
        e = {"type": kind, "day": self.day, **kw}
        self.events.append(e)
        if getattr(self, "out", None):
            json.dump({"events": self.events, "public": self.public}, open(self.out, "w"), ensure_ascii=False, indent=1)
        line = {k: v for k, v in kw.items() if k != "players"}
        print(f"[{kind}] {json.dumps(line, ensure_ascii=False)[:300]}", flush=True)

    def say(self, text):
        self.public.append(text)

    def alive(self, role=None):
        return [p for p in self.players if p.alive and (role is None or p.role == role)]

    def by_name(self, name):
        return next((p for p in self.players if p.name == name), None)

    def system(self, p):
        s = RULES + f"\n\nТебя зовут {p.name}. Твоя роль: {ROLE_RU[p.role].upper()}."
        s += "\nЗа столом: " + ", ".join(x.name for x in self.players) + "."
        if p.role == "mafia":
            mates = [x.name for x in self.players if x.role == "mafia" and x is not p]
            s += "\nТвои напарники по мафии: " + (", ".join(mates) if mates else "нет, ты один") + "."
        return s

    def context(self, p):
        log = "\n".join(self.public) if self.public else "Игра только началась."
        mx = p.cfg.get("log_max_chars", 0)
        cut = False
        while mx and len(log) > mx:   # режем блоками, чтобы кэш префикса жил между обрезками
            log = log[4000:]
            log = log[log.find("\n") + 1:]
            cut = True
        c = "ХОД ИГРЫ:\n" + ("(начало протокола опущено)\n" if cut else "") + log
        c += "\n\nСейчас в игре: " + ", ".join(x.name for x in self.alive()) + "."
        if p.private:
            c += "\n\nТВОИ ЛИЧНЫЕ ЗАМЕТКИ (видишь только ты):\n" + "\n".join(p.private)
        return c

    def ask(self, p, task, fmt):
        user = self.context(p) + "\n\nЗАДАНИЕ: " + task + \
            "\nРассуждения держи короткими: 1-3 предложения. Ответь строго одним JSON без текста вокруг: " + fmt
        if self.delay:
            time.sleep(self.delay)
        try:
            raw = call_llm(p.cfg, self.system(p), user)
        except Exception as e:
            p.fails += 1
            self.ev("error", player=p.name, error=str(e)[:300])
            return {}, ""
        d = parse_json(raw)
        if not d:
            p.fails += 1
        return d, raw

    def pick(self, p, d, raw, options, field="target"):
        """Достаём имя из ответа. Не смогли: None (сбой засчитываем игроку)."""
        names = [o.name for o in options]
        v = str(d.get(field, "")).strip()
        for n in names:
            if n.lower() == v.lower():
                return n
        for n in names:
            if n.lower() in v.lower():
                return n
        if not d:
            found = [n for n in names if n in raw]
            if len(found) == 1:
                return found[0]
        return None

    # ---------- ночь
    def night(self):
        self.ev("phase", phase="night")
        self.say(f"--- Ночь {self.day} ---")
        victim = self.mafia_kill()
        healed = self.doctor_heal()
        self.commissar_check()
        if victim and victim == healed:
            self.say(f"Утро {self.day}: ночью мафия стреляла, но доктор спас жертву. Никто не погиб.")
            self.ev("night_result", victim=None, saved=victim)
        elif victim:
            v = self.by_name(victim)
            v.alive = False
            self.say(f"Утро {self.day}: ночью убит игрок {victim}. Его роль: {ROLE_RU[v.role]}.")
            self.ev("night_result", victim=victim, role=v.role)
        else:
            self.say(f"Утро {self.day}: ночь прошла тихо, никто не погиб.")
            self.ev("night_result", victim=None)

    def mafia_kill(self):
        mafia = self.alive("mafia")
        targets = [p for p in self.alive() if p.role != "mafia"]
        chat, votes = [], []
        for m in mafia:
            task = "Ночь. Мафия выбирает жертву. Кандидаты: " + ", ".join(t.name for t in targets) + "."
            if chat:
                task += "\nНапарники уже написали в тайном чате мафии:\n" + "\n".join(chat)
            d, raw = self.ask(m, task, '{"thoughts": "твои скрытые рассуждения", "message": "реплика напарникам", "target": "имя жертвы"}')
            t = self.pick(m, d, raw, targets)
            msg = str(d.get("message", ""))[:400]
            chat.append(f"{m.name}: {msg} (предлагаю: {t})")
            if t:
                votes.append(t)
            self.ev("mafia_chat", player=m.name, thoughts=str(d.get("thoughts", ""))[:800], message=msg, target=t)
        if not votes:
            return None
        cnt = Counter(votes)
        top = max(cnt.values())
        victim = next(v for v in votes[::-1] if cnt[v] == top)  # при равенстве слово за последним
        for m in mafia:
            m.private.append(f"Ночь {self.day}: мафия стреляла в игрока {victim}.")
        self.ev("mafia_target", target=victim)
        return victim

    def doctor_heal(self):
        docs = self.alive("doctor")
        if not docs:
            return None
        doc = docs[0]
        opts = [p for p in self.alive() if p.name != self.last_heal]
        d, raw = self.ask(doc, "Ночь. Ты доктор. Кого лечишь? Можно себя. Варианты: " + ", ".join(o.name for o in opts) + ".",
                          '{"thoughts": "скрытые рассуждения", "target": "имя"}')
        t = self.pick(doc, d, raw, opts)
        self.last_heal = t
        if t:
            doc.private.append(f"Ночь {self.day}: ты лечил игрока {t}.")
        self.ev("doctor", player=doc.name, thoughts=str(d.get("thoughts", ""))[:800], target=t)
        return t

    def commissar_check(self):
        coms = self.alive("commissar")
        if not coms:
            return
        com = coms[0]
        checked = {x.split()[-2] for x in com.private if "проверка" in x}
        opts = [p for p in self.alive() if p is not com and p.name not in checked] or [p for p in self.alive() if p is not com]
        d, raw = self.ask(com, "Ночь. Ты комиссар. Кого проверяешь? Варианты: " + ", ".join(o.name for o in opts) + ".",
                          '{"thoughts": "скрытые рассуждения", "target": "имя"}')
        t = self.pick(com, d, raw, opts)
        res = None
        if t:
            res = self.by_name(t).role == "mafia"
            com.private.append(f"Ночь {self.day}: проверка показала, что {t} {'МАФИЯ' if res else 'НЕ мафия'}")
        self.ev("commissar", player=com.name, thoughts=str(d.get("thoughts", ""))[:800], target=t, is_mafia=res)

    # ---------- день
    def daytime(self):
        self.ev("phase", phase="day")
        self.say(f"--- День {self.day}: обсуждение ---")
        rounds = 2 if len(self.alive()) <= 7 else 1
        for r in range(rounds):
            order = self.alive()
            self.rng.shuffle(order)
            for p in order:
                d, raw = self.ask(p, "День, обсуждение. Твоя очередь говорить. Скажи столу 2-4 предложения: кого подозреваешь и почему, "
                                     "кому веришь. Опирайся на конкретные слова и голоса других.",
                                  '{"thoughts": "скрытые рассуждения, их никто не увидит", "speech": "то, что ты говоришь вслух"}')
                speech = str(d.get("speech", "")).strip()[:700]
                if not speech and raw and not d:
                    speech = re.sub(r"\s+", " ", raw)[:500]
                if not speech:
                    speech = "(молчит)"
                self.say(f"{p.name}: {speech}")
                self.ev("speech", player=p.name, thoughts=str(d.get("thoughts", ""))[:800], speech=speech)
        # голосование: все отвечают одновременно, не видя чужих голосов
        self.say(f"--- День {self.day}: голосование ---")
        ballots = {}
        for p in self.alive():
            opts = [o for o in self.alive() if o is not p]
            d, raw = self.ask(p, "Голосование. Кого выгоняешь из игры? Варианты: " + ", ".join(o.name for o in opts) +
                              '. Можно воздержаться: тогда target = "никого".',
                              '{"thoughts": "скрытые рассуждения", "target": "имя или никого"}')
            t = self.pick(p, d, raw, opts)
            ballots[p.name] = t
            self.ev("vote", player=p.name, thoughts=str(d.get("thoughts", ""))[:800], target=t)
        self.say("Голоса: " + "; ".join(f"{k} -> {v or 'воздержался'}" for k, v in ballots.items()))
        cnt = Counter(v for v in ballots.values() if v)
        out = None
        if cnt:
            top = cnt.most_common(2)
            if len(top) == 1 or top[0][1] > top[1][1]:
                out = top[0][0]
        if out:
            o = self.by_name(out)
            o.alive = False
            self.say(f"По итогам голосования выбывает {out}. Его роль: {ROLE_RU[o.role]}.")
            self.ev("exile", player=out, role=o.role, tally=dict(cnt))
        else:
            self.say("Голоса разделились, никто не выбывает.")
            self.ev("exile", player=None, tally=dict(cnt))

    def check_win(self):
        m, t = len(self.alive("mafia")), len(self.alive()) - len(self.alive("mafia"))
        if m == 0:
            self.winner = "town"
        elif m >= t:
            self.winner = "mafia"
        return self.winner

    def run(self, max_days=12):
        while not self.winner and self.day < max_days:
            self.day += 1
            self.night()
            if self.check_win():
                break
            self.daytime()
            self.check_win()
        self.ev("end", winner=self.winner or "draw",
                survivors=[p.name for p in self.alive()],
                fails={p.name: p.fails for p in self.players})
        return {"events": self.events, "public": self.public}


if __name__ == "__main__":
    cfg = json.load(open(sys.argv[1]))
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else int(time.time())
    g = Game(cfg, seed)
    out = cfg.get("out", "game.json")
    try:
        res = g.run()
    finally:
        json.dump({"seed": seed, "events": g.events, "public": g.public}, open(out, "w"), ensure_ascii=False, indent=1)
    print("Победитель:", g.winner, "| протокол:", out)
