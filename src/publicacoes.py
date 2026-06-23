"""Loop de performance — registra cortes publicados e puxa as métricas reais.

Liga o corte que o sistema gerou ao post que foi publicado, e coleta a performance real
(o que o algoritmo achou de verdade). É o que faz o sistema parar de adivinhar e aprender.

O que dá pra puxar JÁ (com a YOUTUBE_API_KEY que temos): views, likes, comments de Shorts
do YouTube. Retenção e Instagram precisam de acesso extra (YouTube Analytics OAuth / IG Graph
API) — registrados como upgrade; por enquanto entram como métrica manual se você informar.

Uso:
    python3 src/publicacoes.py registrar <src_video_id> <cut_id> <url_ou_id_do_short> [--plataforma youtube]
    python3 src/publicacoes.py atualizar      # puxa métricas atuais de tudo que é YouTube
"""
import os
import re
import sys
import json
import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
DATA = Path(os.environ.get("DATA_DIR", "./data"))
FB = DATA / "feedback"
PUB = FB / "publicados.jsonl"


def _yt_id(url_ou_id):
    for p in [r"shorts/([^?&/]+)", r"watch\?v=([^?&]+)", r"youtu\.be/([^?&]+)"]:
        m = re.search(p, url_ou_id)
        if m:
            return m.group(1)
    return url_ou_id  # já é o id


def _features_do_corte(src_video_id, cut_id):
    f = DATA / "cuts" / f"{src_video_id}.json"
    if not f.exists():
        return {}
    for c in json.loads(f.read_text(encoding="utf-8")).get("cuts", []):
        if str(c.get("id")) == str(cut_id):
            return {
                "pilar": c.get("pilar_primario"), "tipo": c.get("tipo_corte"),
                "duracao": c.get("duration_seconds"), "score": c.get("score"),
                "tema_match": c.get("tema_alta_match") or [], "falante": c.get("falante_voz") or c.get("person"),
                "tem_bordao": bool(c.get("bordao_presente")),
            }
    return {}


def registrar(src_video_id, cut_id, url, plataforma="youtube", metricas=None):
    FB.mkdir(parents=True, exist_ok=True)
    rec = {
        "ts": datetime.datetime.now().isoformat(),
        "src_video_id": src_video_id, "cut_id": str(cut_id),
        "plataforma": plataforma, "post_id": _yt_id(url) if plataforma == "youtube" else url,
        "url": url, "features": _features_do_corte(src_video_id, cut_id),
        "metricas": metricas or {},
    }
    with open(PUB, "a", encoding="utf-8") as fp:
        fp.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"registrado: corte {cut_id} de {src_video_id} → {rec['post_id']} ({plataforma})")
    return rec


def _carregar():
    if not PUB.exists():
        return []
    return [json.loads(l) for l in open(PUB, encoding="utf-8") if l.strip()]


def atualizar():
    """Puxa métricas atuais dos posts do YouTube (views/likes/comments)."""
    recs = _carregar()
    yt_ids = [r["post_id"] for r in recs if r.get("plataforma") == "youtube"]
    if not yt_ids:
        print("Nada do YouTube pra atualizar."); return
    from googleapiclient.discovery import build
    yt = build("youtube", "v3", developerKey=os.environ["YOUTUBE_API_KEY"])
    stats = {}
    for i in range(0, len(yt_ids), 50):
        r = yt.videos().list(part="statistics", id=",".join(yt_ids[i:i+50])).execute()
        for it in r.get("items", []):
            s = it["statistics"]
            stats[it["id"]] = {"views": int(s.get("viewCount", 0)), "likes": int(s.get("likeCount", 0)),
                               "comments": int(s.get("commentCount", 0))}
    agora = datetime.datetime.now().isoformat()
    for r in recs:
        if r["post_id"] in stats:
            r["metricas"] = {**stats[r["post_id"]], "coletado_em": agora}
    PUB.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in recs) + "\n", encoding="utf-8")
    print(f"métricas atualizadas para {len(stats)} post(s) do YouTube.")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "atualizar":
        atualizar()
    elif len(sys.argv) >= 5 and sys.argv[1] == "registrar":
        plat = "youtube"
        if "--plataforma" in sys.argv:
            plat = sys.argv[sys.argv.index("--plataforma") + 1]
        registrar(sys.argv[2], sys.argv[3], sys.argv[4], plataforma=plat)
    else:
        print(__doc__)
