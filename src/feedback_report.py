"""Loop de feedback: lê as decisões do editor e recomenda ajustes de scoring.

Para cada corte, o editor marca no dashboard: 'cortado' (usou) ou 'descartado' (rejeitou).
Este script cruza essas decisões com as características do corte (score, tipo, pilar,
duração, falante) e mostra ONDE o critério está acertando ou errando — com recomendações.

Rodar:  python3 src/feedback_report.py
"""
import os
import json
import datetime
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECISIONS = os.path.join(ROOT, "data", "feedback", "decisions.jsonl")
REL_DIR = os.path.join(ROOT, "data", "relatorios")


def carregar_decisoes():
    """Última decisão por corte (cortado/descartado)."""
    if not os.path.exists(DECISIONS):
        return []
    ultima = {}
    for linha in open(DECISIONS, encoding="utf-8"):
        linha = linha.strip()
        if not linha:
            continue
        d = json.loads(linha)
        if d.get("status") in ("cortado", "descartado"):
            ultima[f"{d.get('video_id')}:{d.get('cut_id')}"] = d
    return list(ultima.values())


def taxa(decisoes):
    usados = sum(1 for d in decisoes if d["status"] == "cortado")
    total = len(decisoes)
    return usados, total, (usados / total if total else 0.0)


def por(decisoes, chave_fn):
    grupos = defaultdict(list)
    for d in decisoes:
        grupos[chave_fn(d)].append(d)
    return grupos


def banda_score(s):
    s = s or 0
    if s >= 8: return "8.0+"
    if s >= 7: return "7.0–7.9"
    if s >= 6.5: return "6.5–6.9"
    return "6.0–6.4"


def banda_dur(d):
    d = d or 0
    if d < 12: return "<12s"
    if d < 30: return "12–30s"
    if d < 60: return "30–60s"
    return "60s+"


def linha_tabela(rotulo, decisoes):
    u, t, r = taxa(decisoes)
    barra = "█" * round(r * 10) + "░" * (10 - round(r * 10))
    return f"| {rotulo:14} | {t:5} | {u:6} | {barra} {r*100:4.0f}% |"


def gerar():
    dec = carregar_decisoes()
    out = []
    out.append("# Loop de feedback — calibração de cortes\n")
    out.append(f"Gerado em {datetime.datetime.now():%d/%m/%Y %H:%M}\n")

    if not dec:
        out.append("\n**Ainda não há decisões registradas.** Rode o dashboard pelo servidor "
                    "(`python3 src/server.py`), marque alguns cortes como cortado/descartado, "
                    "e rode este relatório de novo.\n")
        _salvar(out); return

    u, t, r = taxa(dec)
    n_alerta = "  ⚠️ amostra pequena, leia como tendência" if t < 20 else ""
    out.append(f"\n## Visão geral\nDecisões: **{t}** · usados: **{u}** · taxa de aproveitamento: **{r*100:.0f}%**{n_alerta}\n")

    def bloco(titulo, grupos, ordem=None):
        out.append(f"\n## {titulo}\n")
        out.append("| categoria | cortes | usados | aproveitamento |")
        out.append("|---|---|---|---|")
        chaves = ordem or sorted(grupos)
        for k in chaves:
            if k in grupos:
                out.append(linha_tabela(str(k), grupos[k]))

    bloco("Por faixa de score", por(dec, lambda d: banda_score(d.get("score"))),
          ordem=["8.0+", "7.0–7.9", "6.5–6.9", "6.0–6.4"])
    bloco("Por tipo", por(dec, lambda d: d.get("tipo") or "?"))
    bloco("Por duração", por(dec, lambda d: banda_dur(d.get("duration"))),
          ordem=["<12s", "12–30s", "30–60s", "60s+"])
    bloco("Por pilar", por(dec, lambda d: d.get("pilar") or "?"))
    bloco("Falante é o personagem-alvo?", por(dec, lambda d: "sim" if d.get("falante_match", True) else "não (convidado)"))

    # --- recomendações automáticas ---
    out.append("\n## Recomendações\n")
    recs = []
    # threshold de score
    bandas = por(dec, lambda d: banda_score(d.get("score")))
    for b in ["6.0–6.4", "6.5–6.9"]:
        if b in bandas:
            _, tb, rb = taxa(bandas[b])
            if tb >= 5 and rb < 0.3:
                recs.append(f"Faixa **{b}** tem só {rb*100:.0f}% de aproveitamento ({tb} cortes) — "
                            f"considere **subir o score mínimo** acima dessa faixa.")
    # tipo
    tipos = por(dec, lambda d: d.get("tipo") or "?")
    if "soundbite" in tipos and "tese_completa" in tipos:
        _, _, rs = taxa(tipos["soundbite"]); _, _, rt = taxa(tipos["tese_completa"])
        if rt - rs > 0.25:
            recs.append(f"**Soundbites** ({rs*100:.0f}%) rendem bem menos que **teses** ({rt*100:.0f}%) — "
                        f"considere gerar menos soundbite ou exigir score maior deles.")
    # falante
    falt = por(dec, lambda d: d.get("falante_match", True))
    if False in falt:
        _, tf, rf = taxa(falt[False])
        if tf >= 3 and rf < 0.2:
            recs.append(f"Cortes de **convidado** (voz ≠ alvo) quase não são usados ({rf*100:.0f}%) — "
                        f"vale **esconder/baixar prioridade** desses por padrão no dashboard.")
    # pilar fraco
    for p, g in por(dec, lambda d: d.get("pilar") or "?").items():
        _, tp, rp = taxa(g)
        if tp >= 5 and rp < 0.25:
            recs.append(f"Pilar **{p}** tem baixo aproveitamento ({rp*100:.0f}%, {tp} cortes) — revisar o critério dele.")

    if recs:
        for rrec in recs:
            out.append(f"- {rrec}")
    else:
        out.append("- Nada gritante ainda. Conforme mais decisões entram, padrões aparecem aqui.")

    _salvar(out)


def _salvar(linhas):
    os.makedirs(REL_DIR, exist_ok=True)
    caminho = os.path.join(REL_DIR, f"feedback_{datetime.date.today():%Y-%m-%d}.md")
    open(caminho, "w", encoding="utf-8").write("\n".join(linhas))
    print("\n".join(linhas))
    print(f"\n[salvo em {caminho}]")


if __name__ == "__main__":
    gerar()
