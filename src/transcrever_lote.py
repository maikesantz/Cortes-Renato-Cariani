"""Transcrição em lote — transcreve as lives de conteúdo, com teto de gasto e dry-run.

Por padrão é DRY-RUN (só mostra o plano e o custo, NÃO gasta). Pra transcrever de verdade,
passe --executar. Para quando bater o teto (--teto), pula o que já está transcrito, e usa o
chunking pra aguentar lives longas.

Fonte da lista: data/temas/lives_conteudo.json (gerado pela triagem_lives.py --ia),
ou todas as lives >1h se a lista não existir.

Uso:
    python3 src/transcrever_lote.py                     # dry-run: plano + custo
    python3 src/transcrever_lote.py --executar --teto 50   # transcreve de verdade até gastar ~R$50
"""
import os
import re
import json
import argparse
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
DATA = Path(os.environ.get("DATA_DIR", "./data"))
LIB = DATA / "library"
TRANSC = DATA / "transcricoes"
USD_H, BRL = 0.04, 5.4


def _secs(iso):
    h = re.search(r"(\d+)H", iso); m = re.search(r"(\d+)M", iso); s = re.search(r"(\d+)S", iso)
    return (int(h.group(1)) * 3600 if h else 0) + (int(m.group(1)) * 60 if m else 0) + (int(s.group(1)) if s else 0)


def _acervo():
    by_id = {}
    for f in LIB.glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        for v in d.get("videos", []):
            by_id[v["video_id"]] = v
    return by_id


def _lista_alvo():
    pref = DATA / "temas" / "lives_conteudo.json"
    if pref.exists():
        return json.loads(pref.read_text(encoding="utf-8"))
    # fallback: todas as lives >1h por views
    vs = [v for v in _acervo().values() if _secs(v.get("duration_iso", "")) >= 3600]
    return [v["video_id"] for v in sorted(vs, key=lambda x: x.get("views", 0), reverse=True)]


def rodar(executar=False, teto=None, limite=None):
    acervo = _acervo()
    ids = _lista_alvo()
    pendentes = [i for i in ids if i in acervo and not (TRANSC / f"{i}.json").exists()]
    if limite:
        pendentes = pendentes[:limite]

    print(f"{'EXECUTANDO' if executar else 'DRY-RUN (não gasta)'} — {len(pendentes)} lives pendentes\n")
    gasto, feitos = 0.0, 0
    for vid in pendentes:
        v = acervo[vid]
        h = _secs(v.get("duration_iso", "")) / 3600
        custo = h * USD_H * BRL
        if teto and gasto + custo > teto:
            print(f"\n[teto de R${teto:.0f} atingido — parando antes de {v['title'][:40]}]")
            break
        gasto += custo
        print(f"  {'+' if executar else '○'} ~{h:.1f}h · R${custo:4.1f} (acum R${gasto:5.1f}) · {v['title'][:46]}")
        if executar:
            try:
                import sys; sys.path.insert(0, str(Path(__file__).parent))
                from download import baixar_audio
                from transcribe import transcrever
                info = baixar_audio(f"https://youtube.com/watch?v={vid}", str(DATA / "audio"))
                t = transcrever(info["path"])
                (TRANSC / f"{vid}.json").write_text(json.dumps(t, ensure_ascii=False), encoding="utf-8")
                feitos += 1
            except Exception as e:
                print(f"      erro: {str(e)[:70]}")

    print(f"\n{'Transcritas: '+str(feitos) if executar else 'Custo estimado do lote'}: R$ {gasto:.0f}")
    if not executar:
        print("Pra transcrever de verdade: --executar  (use --teto N pra limitar o gasto)")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--executar", action="store_true")
    p.add_argument("--teto", type=float, default=None, help="gasto máximo em R$")
    p.add_argument("--limite", type=int, default=None, help="máx de lives")
    a = p.parse_args()
    rodar(executar=a.executar, teto=a.teto, limite=a.limite)
