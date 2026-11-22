// Проверка вёрстки и кадра расчётом, без скриншотов. В консоли страницы игры:
//   await import("/audit.js"); uiAudit()
window.uiAudit = function () {
  const out = [], W = innerWidth, H = innerHeight;
  const vis = el => { const r = el.getBoundingClientRect(), st = getComputedStyle(el); return r.width > 0 && r.height > 0 && st.visibility !== "hidden" && st.display !== "none" && !el.closest("[hidden]"); };
  const rect = el => el.getBoundingClientRect();
  const hit = (a, b) => !(a.right <= b.left + 1 || b.right <= a.left + 1 || a.bottom <= b.top + 1 || b.bottom <= a.top + 1);
  const layer = el => el.closest("#setup") ? "setup" : el.closest(".drawer") ? "drawer" : "stage";
  const top = !$("setup").hidden ? "setup" : !$("drawer").hidden ? "drawer" : "stage";
  const name = el => el.id || (el.textContent || "").trim().slice(0, 18);
  // 1. кнопки и поля: в окне, не налезают, текст не обрезан, не мелкие
  const ctrls = [...document.querySelectorAll("button, select, input")].filter(vis);
  for (const el of ctrls) {
    const r = rect(el), scroll = el.closest(".drawer, #setup .card");
    if (!scroll && (r.left < -1 || r.right > W + 1 || r.top < -1 || r.bottom > H + 1)) out.push("за краем окна: " + name(el));
    if (el.tagName === "BUTTON" && el.scrollWidth > el.clientWidth + 2) out.push("текст кнопки обрезан: " + name(el));
    if (r.height < 28) out.push("слишком низкий элемент: " + name(el) + " " + Math.round(r.height) + "px");
  }
  for (let i = 0; i < ctrls.length; i++) for (let j = i + 1; j < ctrls.length; j++) {
    const a = ctrls[i], b = ctrls[j];
    if (layer(a) !== layer(b)) continue;   // модальный слой закрывает нижний намеренно
    if (hit(rect(a), rect(b))) out.push("налезают: «" + name(a) + "» и «" + name(b) + "»");
  }
  // 2. элементы сцены, закрытые чужим слоем, когда никакое окно не открыто
  if (top === "stage") for (const el of ctrls) {
    const r = rect(el), x = r.left + r.width / 2, y = r.top + r.height / 2, t = document.elementFromPoint(x, y);
    if (t && t !== el && !el.contains(t) && !t.contains(el)) out.push("закрыт другим элементом: " + name(el) + " ← " + (t.id || t.tagName));
  }
  // 3. субтитры и кнопки
  if (top === "stage" && vis($("sub")) && vis($("ctl")) && hit(rect($("sub")), rect($("ctl")))) out.push("субтитры налезают на кнопки");
  // 4. игроки в кадре
  if (top === "stage" && G.players.length) {
    const sub = rect($("sub")); let off = 0, covered = 0;
    for (const p of G.players) {
      const v = p.av.g.position.clone().setY(1.75).project(cam), x = (v.x + 1) / 2 * W, y = (1 - v.y) / 2 * H;
      if (v.z > 1 || x < 0 || x > W || y < 0 || y > H) off++;
      else if (x > sub.left && x < sub.right && y > sub.top && y < sub.bottom) covered++;
    }
    if (off) out.push("за кадром игроков: " + off + " из " + G.players.length);
    if (covered > G.players.length / 3) out.push("под субтитрами игроков: " + covered + " из " + G.players.length);
  }
  return { size: W + "x" + H, layer: top, problems: [...new Set(out)] };
};
