"""Aposta do Dia — o "certeiro" diário pra colar no grupo da equipe.

Destila, numa mensagem curta e baseada em DADO:
  1. o que JÁ está provado que performa (calibração por views reais);
  2. o que está em alta HOJE (tendência real);
  3. a aposta nº1 do dia (o corte que cruza os dois) + comando pronto.

Não é palpite — é o que o público recompensou + o que o mercado quer agora. Pronto pra WhatsApp.
Rodar: python3 src/aposta_do_dia.py
"""
import os
import json
import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
import sys
sys.path.insert(0, str(Path(__file__).parent))

DATA = Path(os.environ.get("DATA_DIR", "./data"))


def _provado():
    f = DATA / "feedback" / "calibragem_titulo.json"
    if not f.exists():
        return []
    pesos = json.loads(f.read_text(encoding="utf-8"))
    fortes = sorted(((n, d["mult"]) for n, d in pesos.items() if d["mult"] >= 1.2), key=lambda x: -x[1])
    return fortes[:3]


def _em_alta():
    f = DATA / "temas" / "ultimo.json"
    if not f.exists():
        return []
    return [t["tema"] for t in json.loads(f.read_text(encoding="utf-8")).get("temas_em_alta", [])][:3]


def _aposta():
    try:
        from oportunidade import analisar
        cortar, _ = analisar()
        if cortar and cortar[0].get("top"):
            c = cortar[0]; v = c["top"][0][1]
            return c["tema"], c["opp"], v
    except Exception:
        pass
    return None


def rodar():
    hoje = datetime.date.today()
    L = [f"🎯 *APOSTA DO DIA* — {hoje:%d/%m}", ""]

    prov = _provado()
    if prov:
        L.append("📊 *Provado (dado real de views):*")
        for n, m in prov:
            L.append(f"  • {n} rende ~{m:.1f}x")
    else:
        L.append("📊 _Sem calibração ainda — rode calibrar.py pra preencher o 'provado'._")

    alta = _em_alta()
    if alta:
        L.append("")
        L.append(f"🔥 *Em alta hoje:* {', '.join(alta)}")

    ap = _aposta()
    L.append("")
    if ap:
        tema, opp, v = ap
        L.append(f"✅ *Aposta nº1:* cortar *{tema}* (oportunidade {opp})")
        L.append(f"   → {v['title'][:50]}")
        L.append(f"   `python3 src/main.py \"https://youtube.com/watch?v={v['video_id']}\" --person renato`")
    else:
        L.append("✅ _Aposta nº1: indexe/transcreva mais do acervo pra encher a fila._")

    L.append("")
    L.append("_Gerado pelo sistema — baseado em performance real + tendência do dia._")

    msg = "\n".join(L)
    out = DATA / "relatorios" / f"aposta_{hoje:%Y-%m-%d}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(msg, encoding="utf-8")
    print(msg)
    print(f"\n[salvo em {out} — é só copiar e colar no grupo]")


if __name__ == "__main__":
    rodar()
