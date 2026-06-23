"""Coleta de tendências REAIS (o que está sendo buscado), multi-fonte.

Fontes:
  - Google Trends (pytrends): termos em ascensão + de volume no Brasil. FONTE PRINCIPAL (dado real).
  - Trending searches do dia (Brasil): contexto geral.
  - Entrada manual (data/temas/manual.json): onde o time coloca o que viu bombar no
    Instagram/TikTok — porque essas plataformas NÃO têm feed público grátis. Sem fingir.

O Claude entra só pra LIMPAR e ESTRUTURAR o dado real em temas do nicho (não pra inventar tendência).

Depende de: pytrends (pip install pytrends).
"""
import os
import json
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# sementes do nicho Cariani (Renato técnico + Tati dores femininas)
SEEDS = [
    "creatina", "ozempic", "lipedema", "jejum intermitente", "whey protein",
    "hipertrofia", "emagrecer", "menopausa", "treino", "dieta",
]


def google_trends(seeds=None, geo="BR", timeframe="now 7-d", max_seeds=6) -> dict:
    """Para cada semente, termos relacionados em ASCENSÃO e de VOLUME no Brasil."""
    from pytrends.request import TrendReq
    seeds = seeds or SEEDS
    pt = TrendReq(hl="pt-BR", tz=180)
    out = {}
    for s in seeds[:max_seeds]:
        try:
            pt.build_payload([s], geo=geo, timeframe=timeframe)
            rq = pt.related_queries().get(s, {})
            termos = []
            rising, top = rq.get("rising"), rq.get("top")
            if rising is not None:
                for _, r in rising.head(6).iterrows():
                    termos.append({"q": r["query"], "tipo": "subindo", "valor": int(r["value"])})
            if top is not None:
                for _, r in top.head(4).iterrows():
                    termos.append({"q": r["query"], "tipo": "volume", "valor": int(r["value"])})
            out[s] = termos
        except Exception as e:
            out[s] = {"erro": str(e)[:80]}
        time.sleep(1)  # respeita o rate limit
    return out


def trending_br() -> list:
    """Buscas em alta no Brasil hoje (geral) — contexto."""
    try:
        from pytrends.request import TrendReq
        pt = TrendReq(hl="pt-BR", tz=180)
        return pt.trending_searches(pn="brazil")[0].tolist()[:20]
    except Exception:
        return []


def entrada_manual() -> dict:
    """O que o time observou no Instagram/TikTok (essas plataformas não têm API livre)."""
    p = Path(os.environ.get("DATA_DIR", "./data")) / "temas" / "manual.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def comentarios_publico(max_videos=5, por_video=8) -> list:
    """Top comentários dos vídeos recentes — demanda DIRETO da audiência (grátis via API)."""
    from googleapiclient.discovery import build
    lib = Path(os.environ.get("DATA_DIR", "./data")) / "library" / "renato_main.json"
    if not lib.exists():
        return []
    vids = json.loads(lib.read_text(encoding="utf-8")).get("videos", [])[:max_videos]
    yt = build("youtube", "v3", developerKey=os.environ["YOUTUBE_API_KEY"])
    coment = []
    for v in vids:
        try:
            r = yt.commentThreads().list(part="snippet", videoId=v["video_id"],
                                         order="relevance", maxResults=por_video, textFormat="plainText").execute()
            for it in r.get("items", []):
                coment.append(it["snippet"]["topLevelComment"]["snippet"]["textDisplay"][:180])
        except Exception:
            continue
    return coment


def concorrentes(seeds=None, dias=7, por_termo=3) -> list:
    """Vídeos do nicho bombando agora no YouTube BR (o que já está viralizando em vídeo)."""
    import datetime
    from googleapiclient.discovery import build
    seeds = seeds or ["creatina", "hipertrofia", "emagrecer ozempic"]
    yt = build("youtube", "v3", developerKey=os.environ["YOUTUBE_API_KEY"])
    after = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=dias)).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = []
    for s in seeds[:3]:
        try:
            r = yt.search().list(part="snippet", q=s, regionCode="BR", relevanceLanguage="pt",
                                 type="video", order="viewCount", publishedAfter=after, maxResults=por_termo).execute()
            for it in r.get("items", []):
                out.append({"termo": s, "titulo": it["snippet"]["title"], "canal": it["snippet"]["channelTitle"]})
        except Exception:
            continue
    return out


def curar(raw_trends: dict, trending: list, manual: dict, comentarios=None, concorrentes_lst=None) -> dict:
    """Claude transforma o dado bruto real em temas limpos do nicho (não inventa tendência)."""
    from anthropic import Anthropic
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

    prompt = f"""Você recebe dados REAIS de tendência (Google Trends Brasil) e organiza para um pipeline de cortes
do Renato Cariani (técnico: treino, suplementação, fisiologia) e da Tati Cariani (dores femininas, nutrição prática).

REGRAS:
- Use SÓ os dados fornecidos. NÃO invente tendência que não está aqui.
- Descarte ruído: nomes de marca soltos, termos sem sentido para o nicho, lojas.
- Agrupe sinônimos (ex.: "creatina creapure" + "creatina chama" -> tema "Creatina").
- Marque nível "alto" para o que está em ASCENSÃO (tipo=subindo), "médio" para volume.
- Para cada tema, sugira 2-4 termos de busca pra achar no acervo de vídeos.

DADOS — Google Trends por semente:
{json.dumps(raw_trends, ensure_ascii=False)}

DADOS — buscas gerais do dia no Brasil:
{json.dumps(trending, ensure_ascii=False)}

DADOS — observado manualmente pelo time (Instagram/TikTok):
{json.dumps(manual, ensure_ascii=False)}

DADOS — comentários recentes do público (dor/pergunta REAL da audiência; pode virar tema):
{json.dumps((comentarios or [])[:30], ensure_ascii=False)}

DADOS — vídeos do nicho bombando agora no YouTube BR (o que já viraliza em vídeo):
{json.dumps(concorrentes_lst or [], ensure_ascii=False)}

Devolva APENAS JSON:
{{
  "temas_em_alta": [
    {{"tema": "string", "motivo": "por que está em alta (1 linha, baseada no dado)", "nivel": "alto|medio",
      "fonte": "google_trends|trending_br|manual", "termos_busca": ["...","..."]}}
  ]
}}"""

    msg = client.messages.create(model=model, max_tokens=2500,
                                 messages=[{"role": "user", "content": prompt}])
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        partes = raw.split("```")
        raw = partes[1] if len(partes) > 1 else raw.lstrip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return json.loads(raw)


def rodar() -> dict:
    import datetime
    data_dir = Path(os.environ.get("DATA_DIR", "./data")) / "temas"
    data_dir.mkdir(parents=True, exist_ok=True)
    hoje = datetime.date.today().strftime("%Y-%m-%d")

    print("Coletando Google Trends (dado real)...")
    raw = google_trends()
    trending = trending_br()
    manual = entrada_manual()
    print("Coletando comentários do público + concorrência...")
    try:
        coment = comentarios_publico()
    except Exception:
        coment = []
    try:
        conc = concorrentes()
    except Exception:
        conc = []
    print("Estruturando temas com Claude...")
    temas = curar(raw, trending, manual, comentarios=coment, concorrentes_lst=conc)
    temas["data"] = hoje
    temas["fontes_brutas"] = {"google_trends": raw, "trending_br": trending}

    (data_dir / f"{hoje}.json").write_text(json.dumps(temas, ensure_ascii=False, indent=2), encoding="utf-8")
    (data_dir / "ultimo.json").write_text(json.dumps(temas, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Temas: {[t['tema'] for t in temas.get('temas_em_alta', [])]}")
    return temas


if __name__ == "__main__":
    rodar()
