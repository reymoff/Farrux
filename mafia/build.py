#!/usr/bin/env python3
"""Собирает страницу-повтор партии: python3 build.py game1.json replay.html"""
import json, sys
src, dst = sys.argv[1], sys.argv[2]
data = json.dumps(json.load(open(src))["events"], ensure_ascii=False).replace("</", "<\\/")
html = r"""<title>Мафия нейросетей</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Golos+Text:wght@400;500;700&family=Unbounded:wght@500;800&family=JetBrains+Mono:wght@400;600&display=swap">
<style>
/* Раскладка: одна колонка протокола, как стенограмма допроса. Ночь темнее дня, скрытые мысли идут курсивом под репликой. */
:root{color-scheme:dark;
 --bg:#12131a;--panel:#1b1d27;--night:#0c0d13;--line:#2c2f3e;--fg:#e7e5dc;--mute:#9a9cab;
 --blood:#e5484d;--town:#4cb5a0;--gold:#d9a441;
 --display:"Unbounded","Arial Black",sans-serif;--body:"Golos Text",system-ui,sans-serif;--mono:"JetBrains Mono",ui-monospace,monospace}
body{background:var(--bg);color:var(--fg);font:16px/1.55 var(--body);
 padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));padding-block:28px 64px}
main{max-width:760px;margin:0 auto;display:flex;flex-direction:column;gap:28px}
h1{font:800 clamp(28px,7vw,46px)/1.05 var(--display);margin:0;text-wrap:balance}
h2{font:500 15px/1.2 var(--display);margin:0;letter-spacing:.04em;text-transform:uppercase}
.lead{color:var(--mute);margin:8px 0 0;max-width:60ch}
.verdict{font:600 14px var(--mono);letter-spacing:.06em;text-transform:uppercase}
.verdict.town{color:var(--town)}.verdict.mafia{color:var(--blood)}
.bar{position:sticky;top:env(safe-area-inset-top,0px);z-index:5;background:var(--bg);padding-block:10px;border-bottom:1px solid var(--line);display:flex;gap:12px;align-items:center;flex-wrap:wrap}
button{font:600 13px var(--mono);color:var(--fg);background:var(--panel);border:1px solid var(--line);border-radius:4px;padding:9px 12px;cursor:pointer}
button[aria-pressed="true"]{background:var(--gold);color:#17130a;border-color:var(--gold)}
button:focus-visible{outline:2px solid var(--gold);outline-offset:2px}
.hint{color:var(--mute);font-size:13px}
.tablewrap{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:14px}
th{font:600 11px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--mute);text-align:left}
th,td{padding:8px 10px 8px 0;border-bottom:1px solid var(--line);vertical-align:top}
td.n{font-family:var(--mono);font-variant-numeric:tabular-nums}
.role{font:600 12px var(--mono);text-transform:uppercase;letter-spacing:.05em}
.role.mafia{color:var(--blood)}.role.doctor,.role.commissar{color:var(--gold)}.role.civilian{color:var(--town)}
.phase{display:flex;flex-direction:column;gap:12px}
.phase.night{background:var(--night);border:1px solid var(--line);padding:16px;border-radius:4px}
.phase h2 span{color:var(--mute)}
.row{display:grid;grid-template-columns:86px 1fr;gap:4px 12px;min-width:0}
.who{font-weight:700}.who small{display:block;font:400 11px var(--mono);color:var(--mute);overflow-wrap:anywhere}
.say{min-width:0;overflow-wrap:anywhere}
.think{grid-column:2;color:var(--mute);font-style:italic;font-size:14px;border-left:2px solid var(--line);padding-left:10px;overflow-wrap:anywhere}
.event{font:600 14px var(--mono);padding:10px 12px;border-left:3px solid var(--blood);background:var(--panel)}
.event.ok{border-color:var(--town)}
.votes{display:flex;flex-wrap:wrap;gap:6px 14px;font:400 13px var(--mono);color:var(--mute)}
.votes b{color:var(--fg);font-weight:600}
body:not(.spoil) .secret{display:none}
@media (max-width:480px){.row{grid-template-columns:1fr}.think{grid-column:1}}
</style>
<main>
<header>
 <div class="verdict" id="verdict"></div>
 <h1>Мафия нейросетей</h1>
 <p class="lead" id="lead"></p>
</header>
<div class="bar">
 <button id="spoil" aria-pressed="false">Показать роли и мысли</button>
 <span class="hint">Без спойлеров видно только то, что слышал стол.</span>
</div>
<section><h2>Кто сидел за столом</h2><div class="tablewrap"><table id="roster"></table></div></section>
<div id="log" style="display:flex;flex-direction:column;gap:28px"></div>
</main>
<script>
const EV = __DATA__;
const RU = {mafia:"мафия",doctor:"доктор",commissar:"комиссар",civilian:"мирный"};
const setup = EV.find(e=>e.type==="setup").players, end = EV.find(e=>e.type==="end")||{};
const P = Object.fromEntries(setup.map(p=>[p.name,p]));
const esc = s => String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const tag = n => `<span class="secret role ${P[n]?.role}"> ${RU[P[n]?.role]||""}</span>`;
const who = n => `<div class="who">${esc(n)}${tag(n)}<small class="secret">${esc(P[n]?.label)}</small></div>`;
const think = t => t ? `<div class="think secret">${esc(Array.isArray(t)?t.join(" "):t)}</div>` : "";

// статистика: голоса против мафии, судьба
const st = Object.fromEntries(setup.map(p=>[p.name,{votes:0,hit:0,fate:"дожил до конца"}]));
for (const e of EV){
  if (e.type==="vote" && e.target){ st[e.player].votes++; if (P[e.target].role==="mafia") st[e.player].hit++; }
  if (e.type==="night_result" && e.victim) st[e.victim].fate = `убит ночью ${e.day}`;
  if (e.type==="exile" && e.player) st[e.player].fate = `изгнан днём ${e.day}`;
}
document.getElementById("verdict").className = "verdict " + (end.winner||"");
document.getElementById("verdict").textContent = end.winner==="town" ? "Победили мирные" : end.winner==="mafia" ? "Победила мафия" : "Партия не доиграна";
document.getElementById("lead").textContent = `${setup.length} открытых моделей разных компаний, дней сыграно: ${end.day||"?"}. Каждая знала только своё имя за столом и свою роль. Ведущий: скрипт.`;
document.getElementById("roster").innerHTML = "<tr><th>Игрок</th><th>Модель</th><th>Роль</th><th>Судьба</th><th>Голоса в мафию</th><th>Сбои</th></tr>" +
 setup.map(p=>{const s=st[p.name];return `<tr><td><b>${esc(p.name)}</b></td><td>${esc(p.label)}</td><td><span class="secret role ${p.role}">${RU[p.role]}</span></td><td>${s.fate}</td><td class="n">${p.role==="mafia"?"·":s.hit+" из "+s.votes}</td><td class="n">${(end.fails||{})[p.name]??0}</td></tr>`}).join("");

let html = "", open = false, ballots = [];
const close = () => { if (open) html += "</section>"; open = false; };
for (const e of EV){
  if (e.type==="phase"){ close(); open = true;
    html += `<section class="phase ${e.phase}"><h2>${e.phase==="night"?"Ночь":"День"} ${e.day} <span>${e.phase==="night"?"город засыпает":"обсуждение"}</span></h2>`; }
  else if (e.type==="mafia_chat") html += `<div class="row secret">${who(e.player)}<div class="say">${esc(e.message)} <span class="role mafia">цель: ${esc(e.target||"?")}</span></div>${think(e.thoughts)}</div>`;
  else if (e.type==="doctor") html += `<div class="row secret">${who(e.player)}<div class="say">Лечит: <b>${esc(e.target||"никого")}</b></div>${think(e.thoughts)}</div>`;
  else if (e.type==="commissar") html += `<div class="row secret">${who(e.player)}<div class="say">Проверяет: <b>${esc(e.target||"никого")}</b>. ${e.is_mafia==null?"":e.is_mafia?"Это мафия.":"Не мафия."}</div>${think(e.thoughts)}</div>`;
  else if (e.type==="night_result") html += e.victim ? `<div class="event">Утром найден убитым: ${esc(e.victim)} (${RU[e.role]})</div>` : `<div class="event ok">${e.saved?"Мафия стреляла, но доктор спас жертву":"Ночь прошла без жертв"}<span class="secret">${e.saved?": "+esc(e.saved):""}</span></div>`;
  else if (e.type==="speech") html += `<div class="row">${who(e.player)}<div class="say">${esc(e.speech)}</div>${think(e.thoughts)}</div>`;
  else if (e.type==="vote") ballots.push(e);
  else if (e.type==="exile"){
    html += `<div class="votes">${ballots.map(b=>`<span><b>${esc(b.player)}</b> → ${esc(b.target||"воздержался")}</span>`).join("")}</div>`;
    html += ballots.map(b=>b.thoughts?`<div class="row secret">${who(b.player)}<div class="say">голос: ${esc(b.target||"воздержался")}</div>${think(b.thoughts)}</div>`:"").join("");
    ballots = [];
    html += e.player ? `<div class="event ${e.role==="mafia"?"ok":""}">Стол изгоняет: ${esc(e.player)} (${RU[e.role]})</div>` : `<div class="event ok">Голоса разделились, никто не изгнан</div>`;
  }
}
close();
document.getElementById("log").innerHTML = html;
const btn = document.getElementById("spoil");
btn.onclick = () => { const on = document.body.classList.toggle("spoil"); btn.setAttribute("aria-pressed", on); btn.textContent = on ? "Скрыть роли и мысли" : "Показать роли и мысли"; };
</script>
"""
open(dst, "w").write(html.replace("__DATA__", data))
print("ok", dst)
