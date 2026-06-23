"""ROTINA 8H — Orquestrador automático.

O que faz, toda manhã às 8h:
1. Pesquisa temas em alta no mundo fitness (via Claude com web search)
2. Atualiza incremental a biblioteca dos 5 canais (só vídeos novos)
3. Detecta vídeos publicados nas últimas N horas
4. Roda o pipeline em até K vídeos novos por canal
5. Busca na biblioteca antiga vídeos antigos que casam com os temas em alta
6. Gera relatório do dia em data/relatorios/AAAA-MM-DD.md

Uso:
    # Roda normal (todo o ciclo)
    python src/daily_routine.py

    # Dry-run: faz as buscas mas NÃO roda o pipeline (zero custo)
    python src/daily_routine.py --dry-run

    # Customiza janela de detecção e quantidade
    python src/daily_routine.py --hours 48 --max-novos 2

    # Pula etapas
    python src/daily_routine.py --skip-temas --skip-index
"""

import os
import sys
import json
import argparse
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# imports locais
sys.path.insert(0, str(Path(__file__).parent))
from library_indexer import indexar_canal, CHANNELS
from library_search import busca_textual

DATA_DIR = Path(os.environ.get("DATA_DIR", "./data"))
LIBRARY_DIR = DATA_DIR / "library"
RELATORIOS_DIR = DATA_DIR / "relatorios"
TEMAS_DIR = DATA_DIR / "temas"


def buscar_temas_alta(dry_run: bool = False) -> dict:
    """Roda temas_em_alta.py e devolve o dict."""
    if dry_run:
        # usa último cacheado
        ultimo = TEMAS_DIR / "ultimo.json"
        if ultimo.exists():
            return json.loads(ultimo.read_text(encoding="utf-8"))
        return {"temas_em_alta": [], "polemicas": [], "viralizadas": []}

    import temas_em_alta
    temas_em_alta.rodar()
    ultimo = TEMAS_DIR / "ultimo.json"
    return json.loads(ultimo.read_text(encoding="utf-8"))


def atualizar_biblioteca_incremental():
    """Atualiza incremental cada canal — só novos vídeos."""
    resultados = {}
    for k in CHANNELS:
        try:
            print(f"\n  ▸ Atualizando {CHANNELS[k]['name']}...")
            antes = 0
            arq = LIBRARY_DIR / f"{k}.json"
            if arq.exists():
                antes = len(json.loads(arq.read_text(encoding="utf-8"))["videos"])

            idx = indexar_canal(k, incremental=True)
            depois = idx.get("total_videos", 0) if idx else antes
            novos = depois - antes
            resultados[k] = {"novos": novos, "total": depois}
            print(f"    ✓ {novos} novos, {depois} total")
        except Exception as e:
            print(f"    ✗ erro: {e}")
            resultados[k] = {"erro": str(e)}
    return resultados


def detectar_videos_novos(horas: int = 24) -> list:
    """Lê os índices e devolve vídeos publicados nas últimas N horas."""
    corte = datetime.now(timezone.utc) - timedelta(hours=horas)
    novos = []
    for f in LIBRARY_DIR.glob("*.json"):
        idx = json.loads(f.read_text(encoding="utf-8"))
        for v in idx.get("videos", []):
            try:
                publicado = datetime.fromisoformat(v["published_at"].replace("Z", "+00:00"))
            except Exception:
                continue
            if publicado >= corte:
                v["channel_key"] = idx["channel_key"]
                v["person"] = idx["person"]
                v["channel_name"] = idx["name"]
                novos.append(v)
    novos.sort(key=lambda v: v["published_at"], reverse=True)
    return novos


def processar_videos_novos(novos: list, temas: dict, max_por_canal: int = 1, dry_run: bool = False):
    """Roda main.py em até max_por_canal vídeos por canal."""
    processados = []
    por_canal = {}
    temas_str = [t["tema"] for t in temas.get("temas_em_alta", [])]

    for v in novos:
        ck = v["channel_key"]
        if por_canal.get(ck, 0) >= max_por_canal:
            continue

        url = f"https://youtube.com/watch?v={v['video_id']}"
        info = {
            "video_id": v["video_id"],
            "title": v["title"],
            "channel": v["channel_name"],
            "person": v["person"],
            "url": url,
            "status": "skipped (dry-run)" if dry_run else "processando"
        }

        if not dry_run:
            try:
                from main import rodar
                rodar(url, v["person"], temas_str)
                info["status"] = "ok"
            except Exception as e:
                info["status"] = f"erro: {e}"
                info["traceback"] = traceback.format_exc()[:500]

        processados.append(info)
        por_canal[ck] = por_canal.get(ck, 0) + 1

    return processados


def cruzar_temas_biblioteca(temas: dict, top_por_tema: int = 3) -> dict:
    """Pra cada tema em alta, busca na biblioteca antiga vídeos que tocam nele."""
    sugestoes = {}
    for t in temas.get("temas_em_alta", []):
        tema = t["tema"]
        # usa os termos_busca ricos do trends (sinônimos/long-tail) + o nome do tema
        query = " ".join(t.get("termos_busca", []) + [tema])
        resultados = busca_textual(query, person_filter=None, top=top_por_tema)
        sugestoes[tema] = [
            {
                "video_id": v["video_id"],
                "title": v["title"],
                "channel": v.get("channel"),
                "person": v.get("person"),
                "views": v.get("views", 0),
                "published_at": v.get("published_at", "")[:10],
                "url": f"https://youtube.com/watch?v={v['video_id']}"
            }
            for _, v in resultados
        ]
    return sugestoes


def gerar_relatorio(temas, atualizacao, videos_novos, processados, sugestoes, dry_run):
    """Gera relatório em markdown."""
    hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    hora = datetime.now(timezone.utc).strftime("%H:%M UTC")
    RELATORIOS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RELATORIOS_DIR / f"{hoje}.md"

    md = [
        f"# Relatório da rotina 8h — {hoje}",
        f"_Gerado às {hora}{'  •  DRY-RUN (sem custo)' if dry_run else ''}_",
        "",
        "## 📈 Temas em alta hoje",
        ""
    ]
    for t in temas.get("temas_em_alta", []):
        md.append(f"- **{t['tema']}** ({t.get('nivel', '?')}) — {t.get('motivo', '')}")
    if temas.get("polemicas"):
        md.append("\n### Polêmicas do dia")
        for p in temas["polemicas"]:
            md.append(f"- **{p.get('titulo', '?')}** — {p.get('resumo', '')}")
    if temas.get("viralizadas"):
        md.append("\n### Viralizadas que ressoam com o público")
        for v in temas["viralizadas"]:
            md.append(f"- {v.get('o_que', '?')} — _{v.get('por_que_ressoa', '')}_")

    md += [
        "",
        "## 📥 Biblioteca atualizada",
        ""
    ]
    for k, r in atualizacao.items():
        nome = CHANNELS.get(k, {}).get("name", k)
        if "erro" in r:
            md.append(f"- ❌ **{nome}** — {r['erro']}")
        else:
            md.append(f"- **{nome}**: +{r['novos']} novos · {r['total']} total")

    md += [
        "",
        f"## 🎬 Vídeos novos detectados (últimas {len(videos_novos)} entries)",
        ""
    ]
    if not videos_novos:
        md.append("_Nenhum vídeo novo no período._")
    else:
        for v in videos_novos[:10]:
            md.append(f"- [{v['title'][:80]}](https://youtube.com/watch?v={v['video_id']}) — _{v['channel_name']}_ · {v['published_at'][:10]}")

    md += [
        "",
        "## ⚙️ Processados pelo pipeline",
        ""
    ]
    if not processados:
        md.append("_Nada processado neste ciclo._")
    else:
        for p in processados:
            badge = {"ok": "✅", "skipped (dry-run)": "⏸️"}.get(p["status"], "❌")
            md.append(f"- {badge} **{p['title'][:70]}** ({p['person']}) — `{p['status']}`")
            md.append(f"  - [{p['url']}]({p['url']})")

    md += [
        "",
        "## 🔁 Sugestões da biblioteca antiga (cross-reference com temas em alta)",
        ""
    ]
    if not sugestoes:
        md.append("_Nenhuma sugestão._")
    for tema, videos in sugestoes.items():
        md.append(f"\n### {tema}")
        if not videos:
            md.append("_Nenhum vídeo antigo casa com esse tema._")
            continue
        for v in videos:
            md.append(f"- [{v['title'][:80]}]({v['url']}) — _{v['channel']}_ · {v['published_at']} · {v['views']:,} views")
            md.append(f"  - `python src/main.py \"{v['url']}\" --person {v['person']}`")

    md += [
        "",
        "---",
        f"_Próximo ciclo: amanhã 8h. Comando manual: `python src/daily_routine.py`_"
    ]

    out_path.write_text("\n".join(md), encoding="utf-8")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Rotina 8h do pipeline de cortes Cariani")
    parser.add_argument("--dry-run", action="store_true",
                        help="Faz buscas e gera relatório, mas NÃO roda o pipeline (zero custo de API paga)")
    parser.add_argument("--hours", type=int, default=24,
                        help="Janela em horas pra detectar vídeos novos (default: 24)")
    parser.add_argument("--max-novos", type=int, default=1,
                        help="Quantos vídeos novos processar por canal (default: 1)")
    parser.add_argument("--skip-temas", action="store_true", help="Pula busca de temas em alta")
    parser.add_argument("--skip-index", action="store_true", help="Pula atualização da biblioteca")
    args = parser.parse_args()

    print(f"\n{'='*70}")
    print(f"  ROTINA 8H — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  {'DRY-RUN ATIVO (zero custo de API paga)' if args.dry_run else 'modo execução real'}")
    print(f"{'='*70}\n")

    # 1. Temas em alta
    print("▸ [1/5] Buscando temas em alta...")
    if args.skip_temas:
        print("  pulado")
        temas = {"temas_em_alta": [], "polemicas": [], "viralizadas": []}
    else:
        temas = buscar_temas_alta(dry_run=args.dry_run)
        print(f"  ✓ {len(temas.get('temas_em_alta', []))} temas detectados")

    # 2. Atualiza biblioteca
    print("\n▸ [2/5] Atualizando biblioteca (incremental)...")
    if args.skip_index:
        print("  pulado")
        atualizacao = {}
    else:
        atualizacao = atualizar_biblioteca_incremental()

    # 3. Detecta vídeos novos
    print(f"\n▸ [3/5] Detectando vídeos publicados nas últimas {args.hours}h...")
    novos = detectar_videos_novos(args.hours)
    print(f"  ✓ {len(novos)} vídeos detectados")

    # 4. Processa novos
    print(f"\n▸ [4/5] Processando novos (até {args.max_novos} por canal)...")
    processados = processar_videos_novos(novos, temas, args.max_novos, args.dry_run)
    print(f"  ✓ {len(processados)} vídeos passados pelo pipeline")

    # 5. Cruzamento biblioteca x temas
    print(f"\n▸ [5/5] Cruzando temas em alta com biblioteca antiga...")
    sugestoes = cruzar_temas_biblioteca(temas, top_por_tema=3)
    print(f"  ✓ sugestões geradas pra {len(sugestoes)} temas")

    # Relatório
    print("\n▸ Gerando relatório...")
    out = gerar_relatorio(temas, atualizacao, novos, processados, sugestoes, args.dry_run)
    print(f"\n{'='*70}")
    print(f"  ✓ Relatório salvo em: {out}")
    print(f"  Abra esse arquivo (.md) pra ver o resumo do dia.")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
