"""Busca semântica + textual na biblioteca indexada.

Dois modos:
  - texto: busca rápida por palavra-chave no título/descrição (grátis, instantâneo)
  - semantico: usa Claude pra interpretar tema e rankear vídeos por relevância (paga API)

Uso:
    python src/library_search.py "creatina retencao"
    python src/library_search.py "lipedema dieta anti-inflamatoria" --semantico
    python src/library_search.py "treino abc natural" --person julio --top 10
"""

import os
import sys
import json
import re
import argparse
from pathlib import Path
from collections import Counter
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(os.environ.get("DATA_DIR", "./data")) / "library"


def carregar_biblioteca(person_filter: str = None) -> list:
    """Carrega TODOS os índices indexados e devolve lista única de vídeos."""
    if not DATA_DIR.exists():
        raise FileNotFoundError(
            f"Pasta {DATA_DIR} não existe. Rode primeiro: python src/library_indexer.py all"
        )

    todos = []
    for f in DATA_DIR.glob("*.json"):
        idx = json.loads(f.read_text(encoding="utf-8"))
        for v in idx.get("videos", []):
            v["channel"] = idx.get("name")
            v["channel_key"] = idx.get("channel_key")
            v["person"] = idx.get("person")
            if person_filter and v["person"] != person_filter:
                continue
            todos.append(v)
    return todos


def normalizar(texto: str) -> str:
    """Lower + remove acentos pra match flexível."""
    import unicodedata
    texto = texto.lower()
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join([c for c in nfkd if not unicodedata.combining(c)])


def score_textual(video: dict, termos: list) -> float:
    """Score simples: conta matches dos termos no título e descrição.
    Match no título vale 3x mais que match na descrição.
    """
    titulo = normalizar(video.get("title", ""))
    descricao = normalizar(video.get("description", ""))
    score = 0
    for t in termos:
        t = normalizar(t)
        if not t:
            continue
        score += titulo.count(t) * 3
        score += descricao.count(t) * 1
    return score


def busca_textual(query: str, person_filter: str = None, top: int = 20) -> list:
    """Busca rápida e gratuita por palavras-chave."""
    videos = carregar_biblioteca(person_filter)
    if not videos:
        return []

    termos = re.split(r"\s+", query.strip())
    scored = []
    for v in videos:
        s = score_textual(v, termos)
        if s > 0:
            scored.append((s, v))

    # ordena: primeiro por score, depois por views (desempate por performance)
    scored.sort(key=lambda x: (x[0], x[1].get("views", 0)), reverse=True)
    return scored[:top]


def busca_semantica(query: str, person_filter: str = None, top: int = 20) -> list:
    """Busca semântica por significado. Usa embedding LOCAL grátis se disponível;
    senão cai pro Claude (pago)."""
    # 1) Caminho grátis/local (embeddings) — objetivo do #5
    try:
        import busca_semantica as _bs
        if _bs.disponivel():
            res = _bs.buscar(query, person=person_filter, top=top)
            if res:
                return res
    except Exception:
        pass

    # 2) Fallback: Claude (pago)
    from anthropic import Anthropic

    videos = carregar_biblioteca(person_filter)
    if not videos:
        return []

    # Faz pré-filtro textual pra reduzir o conjunto antes de mandar pro Claude
    # (limite prático: ~500 vídeos por chamada)
    textuais = busca_textual(query, person_filter, top=500)
    candidatos = [v for _, v in textuais] if textuais else videos[:500]

    # monta lista compacta
    lista_compacta = [
        {
            "id": v["video_id"],
            "t": v["title"],
            "d": v["description"][:200],
            "v": v.get("views", 0)
        }
        for v in candidatos[:300]
    ]

    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

    prompt = f"""Você está vasculhando a biblioteca de vídeos do Renato Cariani / Júlio Balestrin / Tati Cariani.

Tema a buscar: "{query}"

Liste os vídeos da lista abaixo que mais provavelmente tocam nesse tema, do mais ao menos relevante. Considere:
- Match direto no título (peso alto)
- Match conceitual na descrição (peso médio)
- Sinônimos e termos relacionados (ex: "creatina" também aparece como "suplemento", "performance")
- Views como desempate (vídeo já validado pelo público vale mais)

Devolva APENAS um JSON array com os top {top} video IDs, em ordem de relevância. Sem prosa:

["id1", "id2", "id3", ...]

Lista de vídeos:
{json.dumps(lista_compacta, ensure_ascii=False)}"""

    msg = client.messages.create(
        model=model,
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0]

    ids = json.loads(raw)
    by_id = {v["video_id"]: v for v in candidatos}
    return [(100 - i, by_id[vid]) for i, vid in enumerate(ids) if vid in by_id]


def imprimir(resultados: list, query: str):
    """Print formatado dos resultados."""
    if not resultados:
        print(f"\nNenhum vídeo encontrado pra: {query}")
        return

    print(f"\n{'='*80}")
    print(f"  Resultados pra: {query}")
    print(f"{'='*80}\n")
    for score, v in resultados:
        print(f"[{score:>3}] {v['title'][:75]}")
        print(f"      {v.get('channel', '')} • {v['published_at'][:10]} • {v.get('views', 0):,} views")
        print(f"      https://youtube.com/watch?v={v['video_id']}")
        print()


def comando_pipeline(resultados: list, person: str):
    """Imprime sugestão de comando pra rodar pipeline nos top 3."""
    if not resultados:
        return
    print(f"\n{'─'*80}")
    print(f"  Pra processar os top 3 no pipeline, rode:")
    print(f"{'─'*80}\n")
    for _, v in resultados[:3]:
        url = f"https://youtube.com/watch?v={v['video_id']}"
        print(f"  python src/main.py \"{url}\" --person {person}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Busca na biblioteca indexada do ecossistema Cariani")
    parser.add_argument("query", help="Tema/palavra-chave a buscar")
    parser.add_argument("--person", choices=["renato", "julio", "tati"], default=None,
                        help="Filtrar só por um personagem")
    parser.add_argument("--top", type=int, default=20, help="Quantos resultados retornar (default: 20)")
    parser.add_argument("--semantico", action="store_true",
                        help="Usa Claude pra busca inteligente (mais lenta, com custo)")
    args = parser.parse_args()

    if args.semantico:
        print("Busca semântica (via Claude)...")
        resultados = busca_semantica(args.query, args.person, args.top)
    else:
        resultados = busca_textual(args.query, args.person, args.top)

    imprimir(resultados, args.query)

    if args.person and resultados:
        comando_pipeline(resultados, args.person)
