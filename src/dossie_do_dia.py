"""Dossiê do dia — RODA TUDO JUNTO, gera o relatório (.md) E os dados do painel (.js).

Uma execução aciona a engrenagem inteira (nada parado): tendência + concorrência +
sazonalidade + performance + acervo. Salva dois arquivos:
  - data/relatorios/dossie_AAAA-MM-DD.md  (leitura humana)
  - app/painel.js  (window.PAINEL = {...}  → é a FONTE do app/painel)

Rodar: python3 src/dossie_do_dia.py
"""
import os
import re
import glob
import json
import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
import sys
sys.path.insert(0, str(Path(__file__).parent))
ROOT = Path(__file__).parent.parent
DATA = Path(os.environ.get("DATA_DIR", "./data"))
HORARIOS = {"alto": "18h (pico) + 12h", "medio": "12h ou 15h"}


def _direcao(tema, raw):
    chave = tema.split()[0].lower()
    for seed, termos in (raw or {}).items():
        if isinstance(termos, list) and (chave in seed or seed in tema.lower()):
            tipos = [x.get("tipo") for x in termos]
            return "subindo" if tipos.count("subindo") >= tipos.count("volume") else "volume"
    return "—"


def _cuts_prontos(limite=12):
    out = []
    for f in glob.glob(str(DATA / "cuts" / "*.json")):
        if Path(f).name.startswith("index"):
            continue
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8"))
        except Exception:
            continue
        meta = d.get("video_meta", {})
        for c in d.get("cuts", []):
            out.append({
                "headline_post": c.get("headline_post", ""),
                "copy": c.get("copy_short_sugerida", ""),
                "score": c.get("score", 0), "prioridade": c.get("prioridade", c.get("score", 0)),
                "duration": round(c.get("duration_seconds", 0)),
                "tipo": c.get("tipo_corte", ""), "publicavel": bool(c.get("publicavel_sozinho")),
                "pilar": c.get("pilar_primario", ""), "falante": c.get("falante_voz", ""),
                "fidelidade": c.get("fidelidade"),
                "video_id": c.get("video_id", d.get("video_id", "")),
                "video_title": meta.get("title", ""),
                "start_seconds": int(c.get("start_seconds", 0)),
                "start_timestamp": c.get("start_timestamp", ""),
            })
    out.sort(key=lambda x: x.get("prioridade", 0), reverse=True)
    return out[:limite]


def montar():
    hoje = datetime.date.today()
    td = {}
    tp = DATA / "temas" / "ultimo.json"
    if tp.exists():
        td = json.loads(tp.read_text(encoding="utf-8"))
    temas = td.get("temas_em_alta", [])
    raw = (td.get("fontes_brutas", {}) or {}).get("google_trends", {})

    P = {"data": hoje.strftime("%d/%m/%Y")}

    P["temas"] = [{
        "tema": t.get("tema", ""), "nivel": t.get("nivel", ""),
        "direcao": _direcao(t.get("tema", ""), raw), "motivo": t.get("motivo", ""),
        "termos": t.get("termos_busca", []), "horario": HORARIOS.get(t.get("nivel"), "12h"),
    } for t in temas]

    # concorrência (roda junto)
    P["concorrencia"] = []
    try:
        from concorrente_onda import virais
        P["concorrencia"] = [{"views": m["views"], "titulo": m["titulo"], "canal": m["canal"]}
                             for m in virais()[:6]]
    except Exception:
        pass

    # sazonalidade
    P["sazonalidade"] = {"consolidando": [], "novos": [], "esfriando": []}
    try:
        from tendencia_memoria import historico
        _, cons, nov, sum_ = historico()
        P["sazonalidade"] = {"consolidando": [f"{t} ({n}d)" for t, n, _ in cons[:6]],
                             "novos": [t for t, _, _ in nov[:8]],
                             "esfriando": [t for t, _, _ in sum_[:6]]}
    except Exception:
        pass

    # performance
    P["performance"] = []
    cal = DATA / "feedback" / "calibragem_titulo.json"
    if cal.exists():
        pesos = json.loads(cal.read_text(encoding="utf-8"))
        P["performance"] = [{"nome": n, "mult": i["mult"], "n": i["n"]}
                            for n, i in sorted(pesos.items(), key=lambda x: -x[1]["mult"])[:6]]

    # cortar / gravar
    P["cortar"], P["gravar"] = [], []
    try:
        from oportunidade import analisar
        cortar, gravar = analisar()
        for c in cortar:
            v = c["top"][0][1] if c.get("top") else {}
            P["cortar"].append({"tema": c["tema"], "opp": c["opp"], "n": c["n"], "gap": c["gap"],
                                "video_id": v.get("video_id", ""), "video_title": v.get("title", "")})
        P["gravar"] = [{"tema": g["tema"], "nivel": g.get("nivel"), "motivo": g.get("motivo", "")} for g in gravar]
    except Exception:
        pass

    P["cuts"] = _cuts_prontos()
    nv = len(P["cortar"]) or 1
    P["custo"] = f"~R$ {nv*1.5+0.1:.2f}"
    P["stats"] = {"cortes": len(P["cuts"]), "temas": len(P["temas"]),
                  "videos_cortaveis": sum(c["n"] for c in P["cortar"]), "custo": P["custo"]}
    return P


def rodar():
    P = montar()
    # 1) app/painel.js (fonte do painel)
    (ROOT / "app").mkdir(exist_ok=True)
    (ROOT / "app" / "painel.js").write_text("window.PAINEL = " + json.dumps(P, ensure_ascii=False) + ";", encoding="utf-8")
    # 2) markdown (leitura humana)
    md = DATA / "relatorios" / f"dossie_{datetime.date.today():%Y-%m-%d}.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    linhas = [f"# Dossiê do dia — {P['data']}", f"Cortes prontos: {P['stats']['cortes']} · custo: {P['custo']}",
              "\n## Em alta"] + [f"- {t['tema']} [{t['nivel']}/{t['direcao']}] — {t['motivo'][:90]}" for t in P["temas"]]
    linhas += ["\n## Concorrência"] + [f"- {c['views']:,} · {c['titulo'][:50]} ({c['canal']})" for c in P["concorrencia"]]
    linhas += ["\n## Cortar"] + [f"- {c['tema']} (opp {c['opp']}, {c['n']} vídeos)" for c in P["cortar"]]
    linhas += ["\n## Gravar"] + [f"- {g['tema']} — {g['motivo'][:80]}" for g in P["gravar"]]
    md.write_text("\n".join(linhas), encoding="utf-8")
    print(f"✓ Painel gerado: {len(P['cuts'])} cortes, {len(P['temas'])} temas, {len(P['concorrencia'])} virais de concorrente")
    print(f"  app/painel.js  +  {md}")


if __name__ == "__main__":
    rodar()
