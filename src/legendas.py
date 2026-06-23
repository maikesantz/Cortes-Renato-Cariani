"""Legenda SRT a partir da transcrição — de graça, porque a fala já foi transcrita.

Pega os segments de um trecho [start,end] e gera um .srt re-baseado em 00:00 (pronto pro
CutPro / qualquer editor que importe legenda). Legendar costuma ser metade do tempo de edição;
aqui sai junto com o corte, sem trabalho extra.

Uso:
    from legendas import gerar_srt
    gerar_srt("VIDEOID", 159.0, 174.0)   # -> data/clipes/VIDEOID_159-174.srt
"""
import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
DATA = Path(os.environ.get("DATA_DIR", "./data"))


def _ts(x: float) -> str:
    x = max(0.0, x)
    ms = int(round((x - int(x)) * 1000))
    x = int(x)
    return f"{x//3600:02d}:{(x%3600)//60:02d}:{x%60:02d},{ms:03d}"


def gerar_srt(video_id: str, start: float, end: float, out: str = None) -> str:
    transc_path = DATA / "transcricoes" / f"{video_id}.json"
    if not transc_path.exists():
        raise FileNotFoundError(f"Sem transcrição pra {video_id}. Rode o pipeline/garimpo antes.")
    segs = json.loads(transc_path.read_text(encoding="utf-8")).get("segments", [])
    janela = [s for s in segs if s.get("end", 0) > start and s.get("start", 0) < end]

    linhas, i = [], 1
    for s in janela:
        a = max(0.0, s.get("start", 0) - start)
        b = min(end - start, s.get("end", 0) - start)
        if b <= a:
            continue
        linhas.append(f"{i}\n{_ts(a)} --> {_ts(b)}\n{s.get('text', '').strip()}\n")
        i += 1

    out = out or str(DATA / "clipes" / f"{video_id}_{int(start)}-{int(end)}.srt")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text("\n".join(linhas), encoding="utf-8")
    return out


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("Uso: python legendas.py <video_id> <start_seg> <end_seg>")
        sys.exit(1)
    p = gerar_srt(sys.argv[1], float(sys.argv[2]), float(sys.argv[3]))
    print("SRT:", p)
    print(Path(p).read_text(encoding="utf-8")[:400])
