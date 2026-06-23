"""Monitor de performance — o volante que mantém o sistema sempre em alta, com dados.

Roda toda semana (cron). Sem ninguém registrar nada: ele vigia os canais de corte públicos,
guarda um snapshot das views, re-calibra os pesos do score e detecta o que MUDOU —
o que acelerou (faça mais), o que esfriou (segure). Gera um digest e mantém o score alinhado
ao que performa AGORA.

Fluxo:
  1) atualiza o índice dos canais de corte (views novas) — chame antes:
        python3 src/library_indexer.py cariani_tv --incremental
  2) python3 src/monitor.py   -> snapshot + recalibra + drift + digest

Saída: data/relatorios/monitor_AAAA-MM-DD.md  e  data/feedback/snapshots/
"""
import os
import json
import datetime
import statistics
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
import sys
sys.path.insert(0, str(Path(__file__).parent))
from calibrar import calibrar_titulo, _cortes, FEATS, _norm  # reaproveita

DATA = Path(os.environ.get("DATA_DIR", "./data"))
FB = DATA / "feedback"
SNAP = FB / "snapshots"


def _snapshot_atual():
    return {v["video_id"]: {"views": v["views"], "title": v["title"]} for v in _cortes()}


def _ultimo_anterior(hoje):
    if not SNAP.exists():
        return None
    arqs = sorted(p for p in SNAP.glob("20*.json") if p.stem < hoje)
    if not arqs:
        return None
    return json.loads(arqs[-1].read_text(encoding="utf-8"))


def rodar():
    hoje = datetime.date.today().strftime("%Y-%m-%d")
    atual = _snapshot_atual()
    if not atual:
        print("Sem cortes indexados (rode library_indexer.py cariani_tv).")
        return
    anterior = _ultimo_anterior(hoje)
    SNAP.mkdir(parents=True, exist_ok=True)
    (SNAP / f"{hoje}.json").write_text(json.dumps(atual, ensure_ascii=False), encoding="utf-8")

    L = [f"# Monitor de performance — {datetime.date.today():%d/%m/%Y}\n",
         f"Vigiando {len(atual)} cortes publicados.\n"]

    # 1) pesos atuais (calibração por título)
    print("Recalibrando pesos pela performance atual...")
    pesos = calibrar_titulo() or {}

    # 2) drift de views: o que acelerou desde o último snapshot
    if anterior:
        crescimento = []
        for vid, d in atual.items():
            if vid in anterior:
                delta = d["views"] - anterior[vid]["views"]
                if delta > 0:
                    crescimento.append((delta, d["title"]))
        crescimento.sort(reverse=True)
        L.append("\n## 🚀 Cortes que mais aceleraram desde o último monitor")
        for delta, tit in crescimento[:8]:
            L.append(f"- +{delta:,} views — {tit[:60]}")
        if not crescimento:
            L.append("- (sem crescimento medido ainda)")
    else:
        L.append("\n## 🚀 Aceleração\n_Primeiro snapshot — a partir do próximo monitor eu mostro o que está crescendo._")

    # 3) drift de pesos: comparar com o último peso salvo
    hist = FB / "calibragem_hist.json"
    antigos = json.loads(hist.read_text(encoding="utf-8")) if hist.exists() else {}
    L.append("\n## 📊 O que está rendendo (e o que mudou)")
    for nome, info in sorted(pesos.items(), key=lambda x: -x[1]["mult"]):
        mult = info["mult"]
        ant = antigos.get(nome)
        seta = ""
        if ant is not None:
            dif = mult - ant
            if abs(dif) >= 0.15:
                seta = f"  ({'↑ subiu' if dif > 0 else '↓ caiu'} de {ant:.2f}x)"
        marca = "🔥" if mult >= 1.3 else ("❄️" if mult <= 0.85 else "·")
        L.append(f"- {marca} **{nome}**: {mult:.2f}x{seta}")
    hist.write_text(json.dumps({k: v["mult"] for k, v in pesos.items()}, ensure_ascii=False), encoding="utf-8")

    L.append("\n## ✅ Ação")
    fortes = [n for n, i in pesos.items() if i["mult"] >= 1.3]
    fracos = [n for n, i in pesos.items() if i["mult"] <= 0.85]
    if fortes:
        L.append(f"- **Faça mais:** {', '.join(fortes)}")
    if fracos:
        L.append(f"- **Segure:** {', '.join(fracos)}")
    L.append("- Os pesos atualizados já entram no score automaticamente.")

    out = DATA / "relatorios" / f"monitor_{hoje}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L[-12:]))
    print(f"\n[digest salvo em {out}]")


if __name__ == "__main__":
    rodar()
