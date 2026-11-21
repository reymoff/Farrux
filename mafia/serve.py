#!/usr/bin/env python3
"""Локальный запуск стола: python3 serve.py  ->  http://localhost:8765  (то же, что делает api/chat.js на хостинге)"""
import json, os, urllib.request, urllib.error
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "app"))
class H(SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        if self.path != "/api/chat": return self.send_error(404)
        b = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        body = json.dumps({"model": "openai-fast", "messages": b.get("messages", [])[:4], "max_tokens": min(int(b.get("max_tokens", 1200)), 1500), "temperature": b.get("temperature", 0.9), "seed": b.get("seed")}).encode()
        try:
            r = urllib.request.urlopen(urllib.request.Request("https://text.pollinations.ai/openai", body, {"Content-Type": "application/json", "User-Agent": "mafia-table/1.0"}), timeout=120)
            code, out = r.status, r.read()
        except urllib.error.HTTPError as e: code, out = e.code, e.read()
        except Exception as e: code, out = 502, json.dumps({"error": str(e)}).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(out)
ThreadingHTTPServer(("0.0.0.0", 8765), H).serve_forever()
