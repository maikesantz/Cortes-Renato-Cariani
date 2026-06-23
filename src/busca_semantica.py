"""Busca SEMÂNTICA local no acervo — por significado, grátis e offline.

Usa embeddings multilíngues (sentence-transformers, roda no torch que já está instalado).
Calcula o embedding de cada vídeo UMA vez e guarda em cache (data/library/_emb_*.npy);
depois cada consulta é instantânea e sem custo. Pega sinônimo de verdade
(ex.: "suplemento pra massa" acha vídeos de creatina/whey, mesmo sem a palavra exata).

Opcional: precisa de `pip install sentence-transformers`. Se não tiver, o sistema usa
a busca TF-IDF (busca_local.py) automaticamente.
"""
import os
import hashlib
from pathlib import Path
import numpy as np
from dotenv import load_dotenv

load_dotenv()
from busca_local import carregar, _norm

MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
LIB = Path(os.environ.get("DATA_DIR", "./data")) / "library"
_MODELO = None
_CACHE = {}


def disponivel() -> bool:
    try:
        import sentence_transformers  # noqa: F401
        return True
    except Exception:
        return False


def _modelo():
    global _MODELO
    if _MODELO is None:
        from sentence_transformers import SentenceTransformer
        _MODELO = SentenceTransformer(MODEL)
    return _MODELO


def _doc(v: dict) -> str:
    # título conta dobrado; descrição entra curta (boilerplate dilui)
    return _norm(v.get("title", "") + " " + v.get("title", "") + " "
                 + " ".join(v.get("tags", [])) + " " + v.get("description", "")[:300])


def _embeddings(person: str = None):
    key = person or "all"
    if key in _CACHE:
        return _CACHE[key]
    vids = carregar(person)
    if not vids:
        _CACHE[key] = ([], None)
        return _CACHE[key]
    ids = [v["video_id"] for v in vids]
    h = hashlib.md5((MODEL + "|" + key + "|" + ",".join(ids)).encode()).hexdigest()[:10]
    cache = LIB / f"_emb_{key}_{h}.npy"
    if cache.exists():
        emb = np.load(cache)
    else:
        emb = _modelo().encode([_doc(v) for v in vids], batch_size=64,
                               show_progress_bar=False, normalize_embeddings=True)
        try:
            for old in LIB.glob(f"_emb_{key}_*.npy"):
                old.unlink()
        except Exception:
            pass
        np.save(cache, emb)
    _CACHE[key] = (vids, emb)
    return _CACHE[key]


def buscar(query: str, person: str = None, top: int = 10, min_sim: float = 0.30) -> list:
    """[(similaridade, video), ...] por significado. Sem custo de API."""
    vids, emb = _embeddings(person)
    if not vids or emb is None:
        return []
    q = _modelo().encode(_norm(query), normalize_embeddings=True)
    sims = emb @ q
    ordem = np.argsort(sims)[::-1][:top]
    return [(round(float(sims[i]), 3), vids[i]) for i in ordem if sims[i] >= min_sim]


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) or "suplemento pra ganhar massa muscular"
    for s, v in buscar(q, person="renato", top=8):
        print(f"[{s:.2f}] {v.get('views',0):>10,} v — {v['title'][:65]}")
