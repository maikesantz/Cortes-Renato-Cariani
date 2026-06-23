"""Busca DENTRO das transcrições — acha o tema falado em qualquer ponto de uma live/podcast.

As lives do Cariani têm dezenas de temas, mas o título não diz nenhum. Aqui a gente quebra
cada transcrição em janelas de ~75s, faz embedding de cada janela e busca por significado.
Resultado: "Cariani fala de lipedema em 03:42:10 da live X" → ponto exato pra cortar.

Pré-requisito: o vídeo precisa ter sido transcrito (roda no pipeline; lives longas usam o
chunking que já existe). Embeddings via sentence-transformers (local, grátis).
"""
import os
import json
import glob
import hashlib
from pathlib import Path
import numpy as np
from dotenv import load_dotenv

load_dotenv()
from busca_local import _norm

TRANSC = Path(os.environ.get("DATA_DIR", "./data")) / "transcricoes"
JANELA = 75  # segundos por janela de busca
_INDEX = None


def _janelas(segs):
    out, buf, t0 = [], [], None
    for s in segs:
        if t0 is None:
            t0 = s["start"]
        buf.append(s["text"])
        if s["end"] - t0 >= JANELA:
            out.append((t0, s["end"], " ".join(buf)))
            buf, t0 = [], None
    if buf:
        out.append((t0 or 0, segs[-1]["end"], " ".join(buf)))
    return out


def _modelo():
    from busca_semantica import _modelo as m
    return m()


def _fmt(x):
    x = int(x)
    return f"{x//3600:02d}:{(x%3600)//60:02d}:{x%60:02d}"


def _construir():
    """Monta (e cacheia) o índice de janelas + embeddings de todas as transcrições."""
    global _INDEX
    if _INDEX is not None:
        return _INDEX
    arquivos = sorted(glob.glob(str(TRANSC / "*.json")))
    arquivos = [a for a in arquivos if not Path(a).name.startswith("_")]
    if not arquivos:
        _INDEX = ([], None)
        return _INDEX
    assinatura = hashlib.md5("|".join(f"{a}:{os.path.getsize(a)}" for a in arquivos).encode()).hexdigest()[:10]
    cache = TRANSC / f"_idx_{assinatura}.npz"

    chunks = []
    for f in arquivos:
        vid = Path(f).stem
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8"))
        except Exception:
            continue
        for a, b, txt in _janelas(d.get("segments", [])):
            chunks.append({"video_id": vid, "start": a, "end": b, "text": txt})
    if not chunks:
        _INDEX = ([], None)
        return _INDEX

    if cache.exists():
        emb = np.load(cache)["emb"]
    else:
        emb = _modelo().encode([_norm(c["text"]) for c in chunks],
                               normalize_embeddings=True, show_progress_bar=False, batch_size=64)
        try:
            for old in TRANSC.glob("_idx_*.npz"):
                old.unlink()
        except Exception:
            pass
        np.savez(cache, emb=emb)
    _INDEX = (chunks, emb)
    return _INDEX


def buscar(query: str, top: int = 10, min_sim: float = 0.30) -> list:
    chunks, emb = _construir()
    if not chunks or emb is None:
        return []
    q = _modelo().encode(_norm(query), normalize_embeddings=True)
    sims = emb @ q
    ordem = np.argsort(sims)[::-1][:top]
    return [{"video_id": chunks[i]["video_id"], "ts": _fmt(chunks[i]["start"]),
             "start": int(chunks[i]["start"]), "sim": round(float(sims[i]), 3),
             "trecho": chunks[i]["text"][:400]} for i in ordem if sims[i] >= min_sim]


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) or "tensão muscular treino de ombro"
    res = buscar(q)
    if not res:
        print("Nada encontrado (precisa de vídeos transcritos em data/transcricoes/).")
    for r in res:
        print(f"[{r['sim']:.2f}] {r['video_id']} @ {r['ts']} — {r['trecho']}")
