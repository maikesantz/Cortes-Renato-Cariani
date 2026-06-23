"""Score de oportunidade — transforma 'tema em alta' em FILA DE AÇÃO priorizada.

Cruza, para cada tema quente:
  - momentum  (o quanto está subindo, do trends)
  - acervo    (quantos vídeos o Renato já tem sobre isso + views = apetite provado)
  - gap       (há quanto tempo não posta disso → janela inexplorada)

Saída:
  🔪 CORTAR AGORA  — temas quentes com material parado no acervo, ranqueados.
  🎥 GRAVAR        — temas quentes SEM material (buraco de conteúdo = pauta de gravação).

Tudo local e grátis. Rodar: python3 src/oportunidade.py
"""
import os
import re
import json
import math
import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
from busca_local import buscar, _norm


_STOP_TEMA = {"beneficios", "beneficio", "uso", "tipos", "tipo", "escolha", "tecnica", "execucao",
              "dicas", "dica", "como", "para", "com", "sobre", "melhor", "melhores", "guia", "tudo",
              "muito", "mais", "menos", "ajuste", "ajustes", "opcoes", "preco", "nacional"}


def _token_principal(tema: str) -> str:
    """Termo distintivo do tema — ignora palavras genéricas (benefícios, uso, técnica...)."""
    toks = [t for t in re.split(r"[^a-z0-9]+", _norm(tema)) if len(t) >= 4]
    bons = [t for t in toks if t not in _STOP_TEMA]
    pool = bons or toks
    return max(pool, key=len) if pool else _norm(tema)

DATA = Path(os.environ.get("DATA_DIR", "./data"))
SIM_MIN = 0.08        # piso de relevância pra contar como "fala sobre o tema"
MIN_ACERVO = 2        # menos que isso = buraco (gravar)


def _dias_desde(iso: str) -> int:
    try:
        return (datetime.date.today() - datetime.date.fromisoformat(iso[:10])).days
    except Exception:
        return 9999


def _dur_secs(iso: str) -> int:
    h = re.search(r"(\d+)H", iso or ""); m = re.search(r"(\d+)M", iso or ""); s = re.search(r"(\d+)S", iso or "")
    return (int(h.group(1)) * 3600 if h else 0) + (int(m.group(1)) * 60 if m else 0) + (int(s.group(1)) if s else 0)


MIN_CORTAVEL = 90   # abaixo disso é short — não dá pra cortar


def analisar(person: str = None, top_match: int = 25) -> tuple:
    temas_path = DATA / "temas" / "ultimo.json"
    temas = json.loads(temas_path.read_text(encoding="utf-8")).get("temas_em_alta", []) if temas_path.exists() else []
    cortar, gravar = [], []

    for t in temas:
        tema = t.get("tema")
        if not tema:
            continue
        termos = " ".join(t.get("termos_busca", []) + [tema])
        prim = _token_principal(tema)
        matches = []
        for s, v in buscar(termos, person=person, top=top_match):
            if s < SIM_MIN:
                continue
            texto = _norm(v.get("title", "") + " " + v.get("description", "") + " " + " ".join(v.get("tags", [])))
            if prim in texto:                      # exige o termo distintivo do tema
                matches.append((s, v))
        mom = 1.0 if t.get("nivel") == "alto" else 0.6

        if len(matches) >= MIN_ACERVO:
            n = len(matches)
            views = sum(v.get("views", 0) for _, v in matches)
            gap = min(_dias_desde(v.get("published_at", "")) for _, v in matches)
            acervo_n = min(1.0, n / 8)
            gap_n = min(1.0, gap / 90)
            views_n = min(1.0, math.log10(views + 1) / 7)
            opp = round(10 * mom * (0.45 * acervo_n + 0.35 * gap_n + 0.20 * views_n), 1)
            # candidato de corte: prefere vídeo LONGO (cortável), não short
            cortaveis = [m for m in matches if _dur_secs(m[1].get("duration_iso", "")) >= MIN_CORTAVEL]
            top = (cortaveis or matches)[:3]
            cortar.append({"tema": tema, "nivel": t.get("nivel"), "opp": opp, "n": n,
                           "gap": gap, "views": views, "top": top, "tem_longo": bool(cortaveis)})
        else:
            gravar.append({"tema": tema, "nivel": t.get("nivel"), "motivo": t.get("motivo", "")})

    cortar.sort(key=lambda x: -x["opp"])
    gravar.sort(key=lambda x: 0 if x["nivel"] == "alto" else 1)
    return cortar, gravar


def relatorio(person: str = None):
    cortar, gravar = analisar(person)
    L = []
    L.append("# Fila de oportunidade do dia\n")
    L.append(f"_{datetime.datetime.now():%d/%m/%Y %H:%M}_ · acervo: {'todos' if not person else person}\n")

    L.append("\n## 🔪 CORTAR AGORA (tema quente × material parado)\n")
    if cortar:
        L.append("| # | oportunidade | tema | nível | vídeos | sem postar há | melhor candidato |")
        L.append("|---|---|---|---|---|---|---|")
        for i, c in enumerate(cortar, 1):
            best = c["top"][0][1] if c["top"] else {}
            btxt = (best.get("title", "")[:45] + f" ({best.get('views',0):,} v)") if best else "—"
            L.append(f"| {i} | **{c['opp']}** | {c['tema']} | {c['nivel']} | {c['n']} | {c['gap']}d | {btxt} |")
        L.append("\n**Comandos prontos pros 3 melhores do tema nº1:**\n")
        if cortar[0]["top"]:
            for _, v in cortar[0]["top"]:
                L.append(f"- `python3 src/main.py \"https://youtube.com/watch?v={v['video_id']}\" --person renato`")
    else:
        L.append("_Nenhum tema com material suficiente no acervo indexado._")

    L.append("\n## 🎥 GRAVAR — buracos de conteúdo (tema quente, acervo vazio)\n")
    if gravar:
        for g in gravar:
            L.append(f"- **{g['tema']}** ({g['nivel']}) — {g['motivo']}")
        L.append("\n_Esses temas estão sendo buscados mas o canal indexado não tem material. "
                 "Pode estar coberto por outro canal (ex.: Tati) ou é pauta nova pra gravar._")
    else:
        L.append("_Sem buracos — todo tema quente tem material._")

    # --- camada de transcrição: tema em alta DENTRO das lives já transcritas ---
    try:
        import busca_transcricao as bt
        temas = json.loads((DATA / "temas" / "ultimo.json").read_text(encoding="utf-8")).get("temas_em_alta", [])
        achou_trecho = False
        linhas_tr = ["\n## 🎙️ Dentro das lives transcritas (tema → trecho exato)\n"]
        for t in temas:
            q = " ".join(t.get("termos_busca", []) + [t["tema"]])
            hits = bt.buscar(q, top=2, min_sim=0.32)
            if hits:
                achou_trecho = True
                linhas_tr.append(f"**{t['tema']}**")
                for h in hits:
                    linhas_tr.append(f"- {h['video_id']} @ {h['ts']} — \"{h['trecho'][:70]}\"  "
                                     f"`python3 src/main.py \"https://youtube.com/watch?v={h['video_id']}\" --person renato`")
        if achou_trecho:
            L += linhas_tr
        else:
            L.append("\n## 🎙️ Dentro das lives transcritas\n_Sem trecho nas transcrições atuais "
                     "(transcreva mais lives com transcrever_lote.py pra essa camada crescer)._")
    except Exception:
        pass

    out = DATA / "relatorios"
    out.mkdir(parents=True, exist_ok=True)
    caminho = out / f"oportunidades_{datetime.date.today():%Y-%m-%d}.md"
    caminho.write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))
    print(f"\n[salvo em {caminho}]")


if __name__ == "__main__":
    import sys
    relatorio(person=sys.argv[1] if len(sys.argv) > 1 else None)
