"""Servidor local do dashboard + coleta de feedback.

Resolve dois problemas de uma vez:
  - status (cortado/descartado) deixa de viver só no localStorage e passa a persistir em disco
    (sincroniza entre Gustavo, Maldição, etc.);
  - cada decisão vira dado de aprendizado para o loop de feedback (feedback_report.py).

Usa só a biblioteca padrão do Python — não precisa instalar nada.
Rodar:  python3 src/server.py   ->  abre em http://localhost:8000
"""
import os
import json
import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FB_DIR = os.path.join(ROOT, "data", "feedback")
DECISIONS = os.path.join(FB_DIR, "decisions.jsonl")   # histórico (1 linha por evento)
STATUS = os.path.join(FB_DIR, "status.json")          # estado atual por corte


def _carregar_status():
    if os.path.exists(STATUS):
        try:
            return json.load(open(STATUS, encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _gravar_decisao(d):
    os.makedirs(FB_DIR, exist_ok=True)
    d["ts"] = datetime.datetime.now().isoformat()
    # 1) acrescenta ao histórico
    with open(DECISIONS, "a", encoding="utf-8") as f:
        f.write(json.dumps(d, ensure_ascii=False) + "\n")
    # 2) atualiza o estado atual (chave video_id:cut_id)
    st = _carregar_status()
    st[f"{d.get('video_id')}:{d.get('cut_id')}"] = d.get("status")
    json.dump(st, open(STATUS, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=ROOT, **k)

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.rstrip("/") in ("", "/dashboard"):
            self.path = "/dashboard.html"
        if self.path == "/api/decisions":
            return self._json(200, _carregar_status())
        return super().do_GET()

    def do_POST(self):
        if self.path != "/api/decisions":
            return self._json(404, {"erro": "rota desconhecida"})
        try:
            n = int(self.headers.get("Content-Length", 0))
            d = json.loads(self.rfile.read(n) or b"{}")
            _gravar_decisao(d)
            return self._json(200, {"ok": True})
        except Exception as e:
            return self._json(400, {"erro": str(e)})

    def log_message(self, *a):
        pass  # silencioso


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    print(f"Dashboard + feedback em http://localhost:{port}  (Ctrl+C para parar)")
    print(f"Decisões salvas em: {DECISIONS}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
