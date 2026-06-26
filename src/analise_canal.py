"""Análise de MÉTRICAS de um canal de referência (ex.: @cortesdobalestrin).

Estuda o canal ONDE os cortes vão ser postados pra descobrir, com dados reais:
  - duração que mais performa (o tamanho ideal do corte, empírico)
  - palavras/temas de título que puxam views (lift sobre a mediana)
  - cadência de postagem (quantos por semana)
  - engajamento médio (likes+comentários por view)
  - top vídeos (o que estourou)

Gera:
  - data/relatorios/analise_canal_<handle>_<data>.md   (leitura humana)
  - data/setores/<setor>_referencia.json               (perfil que realimenta o scoring)

Só YouTube Data API (barato: ~10 unidades de quota). NÃO baixa vídeo.

Uso:
    python3 src/analise_canal.py @cortesdobalestrin --setor balestrin
    python3 src/analise_canal.py @cortesdobalestrin --limite 300
"""
import os
import re
import json
import argparse
import datetime
import statistics
from collections import Counter
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("DATA_DIR", "./data"))

STOP = set((
    "de da do das dos a o e os as um uma que com para por no na nos nas em ao à aos às "
    "se sua seu suas seus mais menos como qual quais voce vc você não nao sim isso essa esse "
    "esta este pra pro the and is to of in on for you your com sem ja já só so muito muita "
    "ele ela eles elas eu tu meu minha tem ter foi ser são sao vai vou cortes corte"
).split())


def _iso_seg(iso: str) -> int:
    """Duração ISO8601 (PT#H#M#S) → segundos."""
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mi * 60 + s


def _resolver(yt, handle: str) -> dict:
    """Resolve @handle → item de canal (com statistics e uploads)."""
    h = handle.lstrip("@")
    part = "id,snippet,statistics,contentDetails"
    try:
        r = yt.channels().list(part=part, forHandle=h).execute()
        if r.get("items"):
            return r["items"][0]
    except Exception:
        pass
    # fallback: busca por nome (gasta 100 de quota)
    try:
        s = yt.search().list(part="snippet", q=h, type="channel", maxResults=1,
                             regionCode="BR", relevanceLanguage="pt").execute()
        if s.get("items"):
            cid = s["items"][0]["snippet"]["channelId"]
            r = yt.channels().list(part=part, id=cid).execute()
            if r.get("items"):
                return r["items"][0]
    except Exception:
        pass
    return {}


def _videos(yt, uploads: str, limite: int) -> list:
    """Lista os vídeos (mais recentes) com views, likes, comentários e duração."""
    ids, token = [], None
    while len(ids) < limite:
        r = yt.playlistItems().list(part="contentDetails", playlistId=uploads,
                                    maxResults=50, pageToken=token).execute()
        ids += [it["contentDetails"]["videoId"] for it in r.get("items", [])]
        token = r.get("nextPageToken")
        if not token:
            break
    ids = ids[:limite]
    vids = []
    for i in range(0, len(ids), 50):
        r = yt.videos().list(part="snippet,statistics,contentDetails",
                             id=",".join(ids[i:i + 50])).execute()
        for it in r.get("items", []):
            st = it.get("statistics", {})
            vids.append({
                "id": it["id"],
                "title": it["snippet"]["title"],
                "published": it["snippet"]["publishedAt"],
                "views": int(st.get("viewCount", 0)),
                "likes": int(st.get("likeCount", 0)),
                "comments": int(st.get("commentCount", 0)),
                "dur": _iso_seg(it["contentDetails"]["duration"]),
            })
    return vids


def _palavras_que_performam(vids, mediana, top_n=15):
    """Palavras de título com 'lift': frequência nos acima-da-mediana vs no geral."""
    geral, acima = Counter(), Counter()
    n_acima = 0
    for v in vids:
        toks = {w for w in re.findall(r"[a-zà-ú0-9]{3,}", v["title"].lower()) if w not in STOP}
        geral.update(toks)
        if v["views"] >= mediana:
            n_acima += 1
            acima.update(toks)
    out = []
    for w, c in geral.items():
        if c < 2:                       # ignora palavra que aparece 1x só
            continue
        freq_geral = c / len(vids)
        freq_acima = (acima.get(w, 0) / n_acima) if n_acima else 0
        lift = (freq_acima / freq_geral) if freq_geral else 0
        if lift > 1.0:                  # aparece mais nos que performam
            out.append({"palavra": w, "lift": round(lift, 2), "aparicoes": c})
    out.sort(key=lambda x: (x["lift"], x["aparicoes"]), reverse=True)
    return out[:top_n]


def _cadencia(vids):
    """Posts por semana nos últimos 90 dias + intervalo médio entre posts."""
    if len(vids) < 2:
        return {"por_semana": 0, "intervalo_medio_dias": 0}
    datas = sorted(datetime.datetime.fromisoformat(v["published"].replace("Z", "+00:00")) for v in vids)
    gaps = [(datas[i + 1] - datas[i]).total_seconds() / 86400 for i in range(len(datas) - 1)]
    intervalo = statistics.median(gaps) if gaps else 0
    agora = datas[-1]
    recentes = [d for d in datas if (agora - d).days <= 90]
    por_semana = round(len(recentes) / (90 / 7), 1) if recentes else 0
    return {"por_semana": por_semana, "intervalo_medio_dias": round(intervalo, 1)}


def _faixa(seg):
    if seg < 90:
        return "≤1.5min (short)"
    if seg < 300:
        return "1.5–5min (curto)"
    if seg < 600:
        return "5–10min (longo)"
    if seg < 1200:
        return "10–20min (longo+)"
    return ">20min"


def analisar(handle: str, setor: str = None, limite: int = 200) -> dict:
    yt = build("youtube", "v3", developerKey=os.environ["YOUTUBE_API_KEY"])
    ch = _resolver(yt, handle)
    if not ch:
        raise SystemExit(f"Canal não encontrado: {handle}")

    nome = ch["snippet"]["title"]
    cid = ch["id"]
    cstats = ch.get("statistics", {})
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    print(f"=== {nome} ({handle}) ===")
    print(f"    inscritos: {int(cstats.get('subscriberCount', 0)):,} · vídeos: {cstats.get('videoCount', '?')}")
    print(f"    coletando até {limite} vídeos...")

    vids = _videos(yt, uploads, limite)
    if not vids:
        raise SystemExit("Nenhum vídeo coletado.")
    views = [v["views"] for v in vids]
    mediana = statistics.median(views)
    media = statistics.mean(views)

    top = sorted(vids, key=lambda v: -v["views"])[:15]
    # duração que performa: mediana de duração no quartil de cima
    q_top = sorted(vids, key=lambda v: -v["views"])[:max(1, len(vids) // 4)]
    dur_top = statistics.median(v["dur"] for v in q_top)
    dur_geral = statistics.median(v["dur"] for v in vids)

    # engajamento
    eng = [((v["likes"] + v["comments"]) / v["views"]) for v in vids if v["views"] > 0]
    eng_medio = round(statistics.mean(eng) * 100, 2) if eng else 0

    # distribuição por faixa de duração (e a faixa que mais rende)
    faixas = Counter(_faixa(v["dur"]) for v in vids)
    rend = {}
    for v in vids:
        rend.setdefault(_faixa(v["dur"]), []).append(v["views"])
    faixa_rank = sorted(((f, round(statistics.median(vs))) for f, vs in rend.items()),
                        key=lambda x: -x[1])

    palavras = _palavras_que_performam(vids, mediana)
    cad = _cadencia(vids)

    perfil = {
        "canal": nome, "handle": handle, "channel_id": cid,
        "analisado_em": datetime.date.today().isoformat(),
        "amostra": len(vids),
        "inscritos": int(cstats.get("subscriberCount", 0)),
        "views_mediana": int(mediana), "views_media": int(media),
        "duracao_que_performa_seg": int(dur_top),
        "duracao_mediana_geral_seg": int(dur_geral),
        "engajamento_medio_pct": eng_medio,
        "cadencia": cad,
        "faixa_que_mais_rende": faixa_rank[0][0] if faixa_rank else "—",
        "palavras_que_performam": palavras,
        "top_videos": [{"titulo": v["title"], "views": v["views"],
                        "dur_min": round(v["dur"] / 60, 1),
                        "url": f"https://youtu.be/{v['id']}"} for v in top],
    }

    _relatorio(perfil, faixas, faixa_rank)
    if setor:
        _salvar_perfil(setor, perfil)
    return perfil


def _relatorio(p, faixas, faixa_rank):
    d = DATA / "relatorios"
    d.mkdir(parents=True, exist_ok=True)
    h = p["handle"].lstrip("@")
    L = [
        f"# Análise de métricas — {p['canal']} ({p['handle']})",
        f"_{p['analisado_em']} · amostra de {p['amostra']} vídeos · {p['inscritos']:,} inscritos_",
        "",
        "## Resumo (o que os dados dizem)",
        f"- **Views mediana:** {p['views_mediana']:,} · média {p['views_media']:,}",
        f"- **Duração que performa:** ~{p['duracao_que_performa_seg']//60}min "
        f"({p['duracao_que_performa_seg']}s) — mediana de duração no quartil de cima de views",
        f"- **Duração mediana geral:** ~{p['duracao_mediana_geral_seg']//60}min",
        f"- **Faixa que mais rende (views medianas):** {p['faixa_que_mais_rende']}",
        f"- **Engajamento médio:** {p['engajamento_medio_pct']}% (likes+coment / views)",
        f"- **Cadência:** {p['cadencia']['por_semana']} posts/semana "
        f"(intervalo mediano {p['cadencia']['intervalo_medio_dias']} dias)",
        "",
        "## Duração × desempenho (mediana de views por faixa)",
    ]
    for f, med in faixa_rank:
        L.append(f"- {f}: {med:,} views medianas · {faixas.get(f,0)} vídeo(s)")
    L += ["", "## Palavras de título que puxam views (lift > 1)"]
    for w in p["palavras_que_performam"]:
        L.append(f"- **{w['palavra']}** — lift {w['lift']}× ({w['aparicoes']} aparições)")
    L += ["", "## Top 15 vídeos"]
    for v in p["top_videos"]:
        L.append(f"- {v['views']:,} · {v['dur_min']}min · {v['titulo'][:70]}")
    out = d / f"analise_canal_{h}_{p['analisado_em']}.md"
    out.write_text("\n".join(L), encoding="utf-8")
    print(f"\n✓ Relatório: {out}")


def _salvar_perfil(setor, perfil):
    d = DATA / "setores"
    d.mkdir(parents=True, exist_ok=True)
    out = d / f"{setor}_referencia.json"
    out.write_text(json.dumps(perfil, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ Perfil de referência (realimenta o scoring): {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Análise de métricas de um canal de referência")
    ap.add_argument("handle", help="@handle do canal (ex.: @cortesdobalestrin)")
    ap.add_argument("--setor", default=None, help="setor que recebe o perfil (ex.: balestrin)")
    ap.add_argument("--limite", type=int, default=200, help="máx de vídeos a analisar")
    a = ap.parse_args()
    p = analisar(a.handle, a.setor, a.limite)
    print("\n--- destaque ---")
    print(f"Duração ideal pro corte: ~{p['duracao_que_performa_seg']//60}min")
    print(f"Top palavras: {', '.join(w['palavra'] for w in p['palavras_que_performam'][:8])}")
