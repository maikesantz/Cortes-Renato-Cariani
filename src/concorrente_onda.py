"""Onda do concorrente — vídeo bombando no nicho BR → vídeos do Renato pra cortar na onda.

Três fontes de "vídeo viral", combinadas:
  1) LISTA CURADA em `concorrentes.json` (raiz) — canais que você acompanha (por nome/@/link/ID).
  2) AUTO-DESCOBERTA de canais — a cada dia varre o YouTube e acha os canais que estão
     bombando no nicho, incluindo-os automaticamente.
  3) RADAR DE VÍDEO VIRAL (aberto) — pega os PRÓPRIOS vídeos virais do nicho, de QUALQUER
     canal (mesmo fora da lista). É o que captura o viral inesperado pra você surfar.

As fontes 2 e 3 saem da MESMA varredura diária (cacheada 1x/dia → não gasta quota a mais).

Grátis (YouTube API). Rodar: python3 src/concorrente_onda.py
"""
import os
import re
import json
import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
from googleapiclient.discovery import build
from busca_local import buscar, _norm

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "concorrentes.json"
DATA = Path(os.environ.get("DATA_DIR", "./data"))

AUTO_DESCOBERTA = os.environ.get("AUTO_DESCOBERTA", "1") not in ("0", "false", "False")
RADAR_VIRAL = os.environ.get("RADAR_VIRAL", "1") not in ("0", "false", "False")

QUERIES_NICHO = [
    "hipertrofia", "musculação", "treino academia", "ganho de massa muscular",
    "dieta cutting", "fisiculturismo", "suplementação treino", "personal trainer treino",
]
EXCLUIR_NOMES = ("cariani",)

CONCORRENTES_PADRAO = [
    {"nome": "Toguro", "channel_id": "UCEI44xNfQmAukxMf1kW8d5g"},
    {"nome": "Paulo Muzy", "channel_id": "UCUOsr03iLj627hJm55cmIPw"},
    {"nome": "Leandro Twin", "channel_id": "UCPlemwX82_QEWRDC6yYnOCg"},
    {"nome": "Caio Bottura", "channel_id": "UCepEtTIMTtU-MbFHz-pOZMw"},
    {"nome": "Júlio Balestrin"}, {"nome": "Fernando Sardinha"},
    {"nome": "Laércio Refundini"}, {"nome": "Leo Stronda"},
    {"nome": "Carol Borba"}, {"nome": "Gracyanne Barbosa"},
    {"nome": "Felipe Franco"}, {"nome": "4FitClub"},
]

STOP = set("de da do das dos a o e os as um uma que com para por no na nos nas sobre seu sua como "
           "qual quais voce vc nao sim mais menos esse essa isso pra pro the and is to of in".split())


# ----------------------------------------------------------- lista curada
def _carregar_config() -> list:
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(CONCORRENTES_PADRAO, ensure_ascii=False, indent=2),
                               encoding="utf-8")
        return [dict(c) for c in CONCORRENTES_PADRAO]
    try:
        d = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return d if isinstance(d, list) else [dict(c) for c in CONCORRENTES_PADRAO]
    except Exception:
        return [dict(c) for c in CONCORRENTES_PADRAO]


def _salvar_config(lista: list) -> None:
    try:
        CONFIG_PATH.write_text(json.dumps(lista, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _alvo(item: dict) -> tuple:
    cid = (item.get("channel_id") or "").strip()
    if re.fullmatch(r"UC[\w-]{22}", cid):
        return ("id", cid)
    bruto = (item.get("handle") or item.get("link") or item.get("url") or "").strip()
    if bruto:
        m = re.search(r"/channel/(UC[\w-]{22})", bruto)
        if m:
            return ("id", m.group(1))
        m = re.search(r"@([\w.\-]+)", bruto)
        if m:
            return ("handle", "@" + m.group(1))
        return ("handle", "@" + bruto.lstrip("@"))
    nome = (item.get("nome") or "").strip()
    return ("busca", nome) if nome else (None, None)


def _resolver(yt, tipo, valor) -> str:
    if tipo == "id":
        return valor
    if tipo == "handle":
        try:
            r = yt.channels().list(part="id", forHandle=valor.lstrip("@")).execute()
            if r.get("items"):
                return r["items"][0]["id"]
        except Exception:
            pass
    try:
        r = yt.search().list(part="snippet", q=valor, type="channel", maxResults=1,
                             regionCode="BR", relevanceLanguage="pt").execute()
        if r.get("items"):
            return r["items"][0]["snippet"]["channelId"]
    except Exception:
        pass
    return ""


def _curados(yt) -> list:
    config = _carregar_config()
    saida, mudou = [], False
    for item in config:
        nome = item.get("nome") or item.get("handle") or "?"
        cid = item.get("channel_id", "")
        if not re.fullmatch(r"UC[\w-]{22}", cid or ""):
            tipo, valor = _alvo(item)
            cid = _resolver(yt, tipo, valor)
            if cid:
                item["channel_id"] = cid
                mudou = True
        if cid:
            saida.append((nome, cid))
        else:
            print(f"⚠️  Não resolvi o canal de '{nome}' — confira no concorrentes.json")
    if mudou:
        _salvar_config(config)
    return saida


# --------------------------------------------- varredura do nicho (1x/dia)
def _cache_varredura() -> Path:
    return DATA / "feedback" / "varredura_nicho.json"


def varredura_nicho(yt, dias=21, por_query=10, force=False) -> dict:
    """
    UMA varredura do nicho por dia (cacheada). Devolve:
      { "canais": [(nome, channel_id), ...],   # quem aparece nos tops do nicho
        "videos": [ {video_id, titulo, canal, channel_id, views}, ... ] }  # os virais
    Alimenta tanto a auto-descoberta de canais quanto o radar de vídeo viral.
    """
    hoje = datetime.date.today().isoformat()
    cache = _cache_varredura()
    if not force and cache.exists():
        try:
            j = json.loads(cache.read_text(encoding="utf-8"))
            if j.get("data") == hoje:
                return {"canais": [tuple(c) for c in j.get("canais", [])],
                        "videos": j.get("videos", [])}
        except Exception:
            pass

    cutoff = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=dias))
    publishedAfter = cutoff.isoformat().replace("+00:00", "Z")

    ids_video = []
    for q in QUERIES_NICHO:
        try:
            r = yt.search().list(part="snippet", q=q, type="video", order="viewCount",
                                 publishedAfter=publishedAfter, regionCode="BR",
                                 relevanceLanguage="pt", maxResults=por_query).execute()
            for it in r.get("items", []):
                ids_video.append(it["id"]["videoId"])
        except Exception:
            continue
    ids_video = list(dict.fromkeys(ids_video))  # dedup mantendo ordem

    videos, freq = [], {}
    for i in range(0, len(ids_video), 50):
        lote = ids_video[i:i + 50]
        try:
            det = yt.videos().list(part="snippet,statistics", id=",".join(lote)).execute()
        except Exception:
            continue
        for it in det.get("items", []):
            sn, st = it["snippet"], it.get("statistics", {})
            nome = sn.get("channelTitle", "")
            if any(x in nome.lower() for x in EXCLUIR_NOMES):
                continue
            videos.append({
                "video_id": it["id"], "titulo": sn.get("title", ""),
                "canal": nome, "channel_id": sn.get("channelId", ""),
                "views": int(st.get("viewCount", 0)),
            })
            d = freq.setdefault(sn.get("channelId", ""), {"nome": nome, "freq": 0})
            d["freq"] += 1

    videos.sort(key=lambda v: -v["views"])
    canais = [(v["nome"], cid) for cid, v in
              sorted(freq.items(), key=lambda kv: -kv[1]["freq"]) if cid]

    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"data": hoje, "canais": canais, "videos": videos},
                                    ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return {"canais": canais, "videos": videos}


def descobrir_canais(yt, max_novos=15) -> list:
    canais = varredura_nicho(yt)["canais"][:max_novos]
    if canais:
        print(f"🔎 Auto-descoberta: {len(canais)} canais em alta no nicho hoje.")
    return canais


def _todos_os_canais(yt) -> list:
    vistos, saida = set(), []
    for nome, cid in _curados(yt):
        if cid and cid not in vistos:
            vistos.add(cid); saida.append((nome, cid))
    if AUTO_DESCOBERTA:
        for nome, cid in descobrir_canais(yt):
            if cid and cid not in vistos:
                vistos.add(cid); saida.append((nome, cid))
    return saida


# ----------------------------------------------------------- coleta de virais
def virais(dias=30, recentes_por_canal=15, top=10, min_views=20000) -> list:
    """Vídeos virais = (canais acompanhados) + (radar aberto do nicho)."""
    yt = build("youtube", "v3", developerKey=os.environ["YOUTUBE_API_KEY"])
    cutoff = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=dias))
    cand = {}

    # fonte A — uploads recentes dos canais acompanhados
    for nome, cid in _todos_os_canais(yt):
        try:
            ch = yt.channels().list(part="contentDetails", id=cid).execute()
            uploads = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
            pl = yt.playlistItems().list(part="contentDetails", playlistId=uploads,
                                         maxResults=recentes_por_canal).execute()
            ids = [it["contentDetails"]["videoId"] for it in pl.get("items", [])]
            if not ids:
                continue
            det = yt.videos().list(part="snippet,statistics", id=",".join(ids)).execute()
            for it in det.get("items", []):
                pub = it["snippet"]["publishedAt"]
                if datetime.datetime.fromisoformat(pub.replace("Z", "+00:00")) < cutoff:
                    continue
                v = int(it["statistics"].get("viewCount", 0))
                if v >= min_views:
                    cand[it["id"]] = {"titulo": it["snippet"]["title"], "canal": nome,
                                      "views": v, "video_id": it["id"]}
        except Exception:
            continue

    # fonte B — radar de vídeo viral aberto (qualquer canal do nicho)
    if RADAR_VIRAL:
        try:
            for vd in varredura_nicho(yt)["videos"]:
                if vd["views"] >= min_views and vd["video_id"] not in cand:
                    cand[vd["video_id"]] = {"titulo": vd["titulo"], "canal": vd["canal"],
                                            "views": vd["views"], "video_id": vd["video_id"]}
        except Exception:
            pass

    return sorted(cand.values(), key=lambda x: -x["views"])[:top]


def _tokens(titulo: str) -> list:
    return [t for t in _norm(titulo).split() if len(t) >= 5 and t not in STOP]


def relatorio(min_sim=0.10):
    vs = virais()
    L = ["# Onda do concorrente — surfar com o acervo\n", f"_{datetime.datetime.now():%d/%m/%Y %H:%M}_\n"]
    if not vs:
        L.append("\n_Nenhum vídeo recente acima do piso de views no nicho._")
    for m in vs:
        toks = _tokens(m["titulo"])
        brutos = buscar(" ".join(toks), person="renato", top=5) if toks else []
        matches = []
        for s, v in brutos:
            if s < min_sim:
                continue
            texto = _norm(v.get("title", "") + " " + " ".join(v.get("tags", [])))
            if any(t in texto for t in toks):
                matches.append((s, v))
        L.append(f"\n### 🌊 {m['views']:,} views — \"{m['titulo'][:65]}\" — {m['canal']}")
        if matches:
            L.append("Renato tem material pra surfar — corta:")
            for s, v in matches[:3]:
                L.append(f"- `python3 src/main.py \"https://youtube.com/watch?v={v['video_id']}\" "
                         f"--person renato`  · {v['title'][:46]} ({v.get('views',0):,} v)")
        else:
            L.append("_Sem material no acervo → pauta pra gravar na onda._")
    out = DATA / "relatorios"
    out.mkdir(parents=True, exist_ok=True)
    caminho = out / f"onda_concorrente_{datetime.date.today():%Y-%m-%d}.md"
    caminho.write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))
    print(f"\n[salvo em {caminho}]")


if __name__ == "__main__":
    relatorio()
