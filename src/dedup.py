"""Dedup — evita transcrever/cortar o mesmo conteúdo duas vezes.

Dois problemas:
  1) canais de CORTES (CarianiTV, RCC) são segmentos do conteúdo-fonte (canal principal/lives).
     Como cortes são curtos (<10min), a MINERAÇÃO (que só toca vídeos longos) já os exclui sozinha.
  2) às vezes o MESMO vídeo longo (ex.: um IRONCAST) está em dois canais. Aqui a gente sinaliza
     esses pares por título+duração parecidos, pra você não transcrever a mesma live duas vezes.

Dedup 100% confiável é por transcrição (a fala bate), mas isto pega a maioria de graça.
Rodar: python3 src/dedup.py
"""
import os
import re
import json
import difflib
import unicodedata
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
LIB = Path(os.environ.get("DATA_DIR", "./data")) / "library"

# canais que são predominantemente CORTES (saída), não fonte
DERIVADOS = {"renato_cortes", "cariani_tv"}


def _secs(iso):
    h = re.search(r"(\d+)H", iso); m = re.search(r"(\d+)M", iso); s = re.search(r"(\d+)S", iso)
    return (int(h.group(1)) * 3600 if h else 0) + (int(m.group(1)) * 60 if m else 0) + (int(s.group(1)) if s else 0)


def _norm(s):
    s = (s or "").lower()
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _carregar():
    out = []
    for f in LIB.glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        for v in d.get("videos", []):
            v["_ch"] = d.get("channel_key"); v["_dur"] = _secs(v.get("duration_iso", ""))
            out.append(v)
    return out


def duplicatas_longas(min_h=1.0, sim_min=0.72):
    """Pares de vídeos LONGOS em canais diferentes, com título+duração parecidos."""
    longos = [v for v in _carregar() if v["_dur"] >= min_h * 3600]
    pares = []
    for i in range(len(longos)):
        for j in range(i + 1, len(longos)):
            a, b = longos[i], longos[j]
            if a["_ch"] == b["_ch"]:
                continue
            if abs(a["_dur"] - b["_dur"]) > 120:        # duração tem que bater (±2min)
                continue
            r = difflib.SequenceMatcher(None, _norm(a["title"]), _norm(b["title"])).ratio()
            if r >= sim_min:
                pares.append((round(r, 2), a, b))
    return sorted(pares, key=lambda x: -x[0])


def relatorio():
    print("# Dedup — duplicatas e canais de cortes\n")
    todos = _carregar()
    por_canal = {}
    for v in todos:
        por_canal.setdefault(v["_ch"], []).append(v)
    print("## Composição dos canais indexados (a maioria é short — em todos)")
    for ch, vs in por_canal.items():
        curtos = sum(1 for v in vs if v["_dur"] < 600)
        longos = sum(1 for v in vs if v["_dur"] >= 3600)
        print(f"  {ch:16} {len(vs):4} vídeos · {100*curtos/len(vs):3.0f}% shorts (<10min) · {longos} longos (>1h)")
    print("\n  Regra de mineração: transcreve SÓ os longos (>1h). Os shorts/cortes (a maioria, "
          "em qualquer canal) ficam de fora sozinhos — não há risco de transcrever corte duas vezes.\n")

    pares = duplicatas_longas()
    print(f"## Vídeos LONGOS possivelmente duplicados entre canais ({len(pares)})")
    if not pares:
        print("  (nenhum par óbvio por título+duração — o que houver, o dedup por transcrição pega)")
    for r, a, b in pares[:15]:
        print(f"  [{r}] {a['_ch']}: {a['title'][:38]}  ==  {b['_ch']}: {b['title'][:38]}")


if __name__ == "__main__":
    relatorio()
