// Краш-тест стола. Гоняет партии без сети прямо на странице игры:
// модели отвечают случайно (верно, мусором, пусто, ошибкой), ведущий жмёт случайные кнопки.
// После каждого шага проверяются правила игры. Запуск в консоли страницы:
//   await import("/crash.js"); await crashTest(200)
window.crashTest = async function (games = 100, seed = 1) {
  let s = seed >>> 0;
  const rand = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
  const ri = n => Math.floor(rand() * n), one = a => a[ri(a.length)];
  const problems = [], stats = { games: 0, steps: 0, town: 0, mafia: 0, stopped: 0, swaps: 0, ties: 0, saves: 0 };
  const bad = (msg, extra) => { if (problems.length < 80) problems.push(msg + (extra ? " | " + extra : "")); };
  const onErr = e => bad("исключение: " + (e.message || (e.reason && e.reason.message) || e.reason));
  addEventListener("error", onErr); addEventListener("unhandledrejection", onErr);

  for (const k in PROV) { PROV[k].gap = 0; PROV[k].dead = false; }
  const keys = ["kGroq", "kGemini", "kOpenrouter", "kHf"], saved = {};
  for (const k of keys) { saved[k] = localStorage.getItem(k); if (!saved[k]) localStorage.setItem(k, "test"); }
  const realCall = callLLM, realShow = show;
  let chaos = 0.25;
  window.callLLM = async function (p, sys, user) {
    if (user.includes("persona")) { if (rand() < 0.15) throw new Error("тест: не ответила"); return rand() < 0.2 ? "мусор без json" : '{"persona":"тест","gender":"' + one(["мужской", "женский", ""]) + '"}'; }
    if (!p.alive) bad("спросили выбывшего игрока", p.name);
    const r = rand();
    if (r < chaos * 0.25) throw new Error("тест: модель упала");
    if (r < chaos * 0.45) return "просто текст, никакого json";
    if (r < chaos * 0.6) return "{}";
    if (r < chaos * 0.75) return '{"thoughts":"x","target":"Никто Такой","speech":"","choice":"","action":"стрелять"}';
    if (r < chaos * 0.85) return '{"thoughts":"x","target":"' + p.name + '","speech":"голосую за себя","action":"стрелять","choice":"выгнать"}';
    const al = G.players.filter(x => x.alive && x !== p), t = al.length ? one(al).name : "";
    return JSON.stringify({ thoughts: "думаю", speech: "подозреваю " + t, message: "бьём " + t, target: t, emotion: one(["злость", "печаль", "радость", "удивление", "спокойно", "xx"]), action: one(["проверить", "стрелять", "стрелять", ""]), choice: one(["выгнать", "оставить", "не знаю"]) });
  };
  window.show = async function (p, text, think, pub, alt) { if (String(text).startsWith("Сбой шага")) bad(String(text), "фаза " + G.phase); return realShow(p, text, think, pub, alt); };
  const soundWas = $("sound").value; $("sound").value = "0";
  const junk = /undefined|\[object|NaN|\u0000/;

  const check = where => {
    const names = G.players.map(p => p.name);
    if (new Set(names).size !== names.length) bad("одинаковые имена", names.join(","));
    for (const p of G.players) {
      if (!p.av || !p.av.g) bad("нет аватара", p.name);
      else if (![p.av.g.position.x, p.av.g.position.z, p.av.ang, p.av.tAng].every(isFinite)) bad("аватар улетел (NaN)", p.name);
      if (!p.name || junk.test(p.name)) bad("битое имя", String(p.name));
    }
    if (G.phase === "lobby" || G.phase === "start") return;
    if (alive("doctor").length > 1) bad("два доктора", where);
    if (alive("commissar").length > 1) bad("два комиссара", where);
    if (alive("mafia").filter(m => m.don).length > 1) bad("два дона", where);
    for (const [k, v] of Object.entries(G.ballots)) {
      if (!byName(k)) bad("голос от несуществующего", k);
      if (v && !byName(v)) bad("голос против несуществующего", v);
      if (v && v === k) bad("голос против себя", k);
    }
    if (G.night) {
      const v = G.night.victim && byName(G.night.victim);
      if (G.night.victim && !v) bad("жертва мафии не существует", G.night.victim);
      if (v && v.role === "mafia") bad("мафия стреляет в мафию", v.name);
      if (G.night.shot && G.day < 2 && G.phase === "night") bad("комиссар стрелял в первую ночь");
      if (G.night.heal && !byName(G.night.heal)) bad("доктор лечит несуществующего", G.night.heal);
    }
    const j = G.pub.find(l => junk.test(l)); if (j) bad("мусор в протоколе", j.slice(0, 120));
    if (G.phase === "over" && G.winner !== "stopped") {
      const m = alive("mafia").length, t = alive().length - m;
      if (G.winner === "town" && m !== 0) bad("победа мирных при живой мафии");
      if (G.winner === "mafia" && m < t) bad("победа мафии при меньшинстве", m + " против " + t);
      if (!G.winner) bad("конец игры без победителя");
    }
  };

  for (let g = 0; g < games && problems.length < 80; g++) {
    chaos = [0, 0.15, 0.3, 0.6, 0.95][g % 5];
    const n = 4 + ri(13), host = g % 3 === 2;   // каждая третья партия с буйным ведущим
    for (const k in PROV) PROV[k].dead = rand() < 0.15 && k !== "pollinations";
    if (g % 4 === 0) for (const k in flaky) delete flaky[k];   // память о сбойных моделях живёт несколько партий
    $("setup").hidden = true; $("drawer").hidden = true;
    $("sPlayers").value = n; $("sDon").value = rand() < 0.7 ? "1" : "0"; $("sFill").value = rand() < 0.7 ? "1" : "0"; setupRefresh();
    const mm = $("sMafia").options; $("sMafia").value = mm[ri(mm.length)].value;
    applySetup();
    if (G.phase !== "lobby" && G.phase !== "over") { bad("партия не закончилась перед новой", G.phase); $("bEnd").click(); }
    await fillTable();
    if (filling) bad("рассадка не завершилась");
    if (G.players.length < 4) bad("за столом меньше четырёх", String(G.players.length));
    if ($("sFill").value === "1" && G.players.length !== n) bad("игроков не столько, сколько выбрано", G.players.length + " вместо " + n);
    if (G.players.some(p => p.failed)) bad("за столом молчащая модель");
    check("после рассадки");
    let steps = 0, lastPub = 0, dealt = false; const heals = {};
    while (steps++ < 1500) {
      if (G.phase === "over" && !G.queue.length) break;
      const phaseBefore = G.phase, healBefore = G.lastHeal;
      if (host && G.phase !== "lobby" && !G.busy) {
        const r = rand(), al = alive();
        if (r < 0.03 && al.length > 3) kick(one(al).name);
        else if (r < 0.06) skipPhase();
        else if (r < 0.10) await redo();
        else if (r < 0.13) { await replay(-1); await replay(1); }
        else if (r < 0.16 && al.length) { if (swapModel(one(al), "тест")) stats.swaps++; }
        else if (r < 0.18 && G.players.length < 16) await addPlayer("pollinations", "openai-fast", oneOnly(one(["civilian", "mafia", "doctor", "commissar"])), "", "");
        else if (r < 0.185) $("bEnd").click();
        else if (r < 0.2) { $("spoil").value = $("spoil").value === "1" ? "0" : "1"; $("spoil").onchange(); }
        check("после действия ведущего");
        if (G.phase === "over" && !G.queue.length) break;
      }
      if (G.pending) { bad("игра ждёт ведущего (pending)", JSON.stringify(G.pending)); G.pending = null; }
      await next();
      stats.steps++;
      if (G.busy) bad("после шага игра осталась занятой");
      if (!dealt && G.phase === "start") {
        dealt = true;
        const m = G.players.filter(p => p.role === "mafia").length, d = G.players.filter(p => p.role === "doctor").length, c = G.players.filter(p => p.role === "commissar").length;
        if (d !== 1 || c !== 1) bad("раздача: докторов " + d + ", комиссаров " + c, "игроков " + G.players.length);
        if (m < 1 || m * 2 >= G.players.length) bad("раздача: мафий " + m + " на " + G.players.length);
        if (G.useDon && G.players.filter(p => p.don).length !== 1) bad("раздача: донов не один");
      }
      if (!host && G.night && G.night.heal){ if (heals[G.day - 1] && heals[G.day - 1] === G.night.heal && heals[G.day] === undefined) bad("доктор лечит одного и того же вторую ночь подряд", G.night.heal); heals[G.day] = G.night.heal; }
      for (let i = lastPub; i < G.pub.length; i++) { if (/Голоса равны/.test(G.pub[i])) stats.ties++; if (/спас/.test(G.pub[i])) stats.saves++; }
      lastPub = G.pub.length;
      check("шаг " + steps + " фаза " + G.phase);
    }
    if (!(G.phase === "over" && !G.queue.length)) bad("партия не закончилась за 1500 шагов", "фаза " + G.phase + ", день " + G.day + ", живых " + alive().length);
    stats.games++; stats[G.winner] = (stats[G.winner] || 0) + 1;
    await next();   // после конца должно открыться окно новой партии
    if ($("setup").hidden) bad("после конца игры не открылось окно новой партии");
  }
  window.callLLM = realCall; window.show = realShow; $("sound").value = soundWas;
  removeEventListener("error", onErr); removeEventListener("unhandledrejection", onErr);
  for (const k of keys) if (!saved[k]) localStorage.removeItem(k);
  for (const k in PROV) PROV[k].dead = false;
  return { stats, problems: [...new Set(problems)] };
};
