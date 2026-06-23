"""Garimpo de tema nas lives — tema quente → trecho exato pra cortar.

Fluxo:
  1) busca o tema no que JÁ foi transcrito (grátis, instantâneo) → trechos com timestamp;
  2) lista as LIVES candidatas (longas, ainda não transcritas) ranqueadas por relevância+views;
  3) opcional (--transcrever N): transcreve as N melhores candidatas (chunking aguenta horas)
     e refaz a busca — aí acha o tema dentro delas, com o ponto exato pra cortar.

Por que sob demanda: são centenas de lives de horas; transcrever tudo é caro. Você minera
só quando o tema esquenta, e o que transcreveu fica no acervo de busca pra sempre.

Uso:
    python3 src/garimpo.py "creatina"                 # grátis: o que já dá pra achar + candidatas
    python3 src/garimpo.py "creatina" --transcrever 2 # minera as 2 melhores lives e re-busca
"""
import os
import re
import json
import argparse
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
import busca_transcricao as bt
from busca_local import carregar, _norm

DATA = Path(os.environ.get("DATA_DIR", "./data"))
TRANSC = DATA / "transcricoes"


def _secs(iso):
    h = re.search(r"(\d+)H", iso); m = re.search(r"(\d+)M", iso); s = re.search(r"(\d+)S", iso)
    return (int(h.group(1)) * 3600 if h else 0) + (int(m.group(1)) * 60 if m else 0) + (int(s.group(1)) if s else 0)


def _transcrito(vid):
    return (TRANSC / f"{vid}.json").exists()


def candidatas(tema, person=None, min_h=1.0, top=6):
    toks = [t for t in _norm(tema).split() if len(t) >= 4]
    vids = [v for v in carregar(person)
            if _secs(v.get("duration_iso", "")) >= min_h * 3600 and not _transcrito(v["video_id"])]
    def rel(v):
        t = _norm(v.get("title", "") + " " + " ".join(v.get("tags", [])))
        return sum(t.count(x) for x in toks)
    vids.sort(key=lambda v: (rel(v), v.get("views", 0)), reverse=True)
    return vids[:top]


def minerar(tema, transcrever=0, person=None):
    pessoa = person or "renato"
    print(f"# Garimpo: \"{tema}\"\n")

    def mostra_hits(hits):
        if not hits:
            print("  (nada nas transcrições atuais)")
        for h in hits:
            print(f"  • {h['video_id']} @ {h['ts']}  (sim {h['sim']}) — {h['trecho'][:85]}")
            print(f"      corta: python3 src/main.py \"https://youtube.com/watch?v={h['video_id']}\" --person {pessoa}")

    print("## Trechos já encontrados (transcrições existentes)")
    mostra_hits(bt.buscar(tema, top=8))

    cands = candidatas(tema, person)
    print(f"\n## Lives candidatas pra minerar (longas, não transcritas) — {len(cands)} melhores")
    for v in cands:
        print(f"  ~{_secs(v['duration_iso'])//3600}h · {v.get('views',0):>10,} v · {v['title'][:50]}  [{v['video_id']}]")
    if cands and not transcrever:
        horas = sum(_secs(v["duration_iso"]) for v in cands) / 3600
        print(f"\n  Pra minerar as melhores: python3 src/garimpo.py \"{tema}\" --transcrever 2")
        print(f"  (custo ~R$ {horas*0.04*5.4/len(cands)*2:.0f} pra 2 lives)")

    if transcrever > 0 and cands:
        from download import baixar_audio
        from transcribe import transcrever as _tr
        for v in cands[:transcrever]:
            vid = v["video_id"]
            print(f"\n>> transcrevendo {vid} — {v['title'][:40]} ...")
            try:
                info = baixar_audio(f"https://youtube.com/watch?v={vid}", str(DATA / "audio"))
                t = _tr(info["path"])
                (TRANSC / f"{vid}.json").write_text(json.dumps(t, ensure_ascii=False), encoding="utf-8")
            except Exception as e:
                print(f"   erro: {str(e)[:80]}")
        bt._INDEX = None  # invalida o cache de busca
        print("\n## Re-busca depois de minerar:")
        mostra_hits(bt.buscar(tema, top=8))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("tema")
    p.add_argument("--transcrever", type=int, default=0)
    p.add_argument("--person", default=None)
    a = p.parse_args()
    minerar(a.tema, a.transcrever, a.person)
