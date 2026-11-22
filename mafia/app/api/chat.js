// Посредник для модели без ключа: браузер -> этот сервер -> text.pollinations.ai.
// Пропускает только одну бесплатную модель и ограничивает размер запроса.
export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ error: "POST only" });
  // только со своей страницы: чужие сайты не смогут гонять запросы через этот адрес
  const origin = req.headers.origin;
  if (origin) { try { if (new URL(origin).host !== req.headers.host) return res.status(403).json({ error: "forbidden" }); } catch (e) { return res.status(403).json({ error: "forbidden" }); } }
  const b = req.body || {};
  const messages = Array.isArray(b.messages) ? b.messages.slice(0, 4) : [];
  if (!messages.length || JSON.stringify(messages).length > 60000) return res.status(400).json({ error: "bad request" });
  try {
    const r = await fetch("https://text.pollinations.ai/openai", {
      method: "POST",
      headers: { "Content-Type": "application/json", "User-Agent": "mafia-table/1.0" },
      body: JSON.stringify({ model: "openai-fast", messages, max_tokens: Math.min(+b.max_tokens || 1200, 1500), temperature: Number.isFinite(+b.temperature) && b.temperature !== null && b.temperature !== "" ? Math.min(Math.max(+b.temperature, 0), 1.5) : 0.9, seed: +b.seed || undefined }),
    });
    const text = await r.text();
    res.status(r.status).setHeader("Content-Type", "application/json").send(text);
  } catch (e) {
    res.status(502).json({ error: String(e.message || e) });
  }
}
