"""Busca local no acervo — grátis, offline, sem custo recorrente.

Usa TF-IDF (pondera termos informativos, entende bigramas) em vez de contagem crua de
palavra. Roda 100% local com scikit-learn (já vem instalado). Sem chamar API por consulta.

(Upgrade futuro opcional: trocar TF-IDF por embeddings neurais p/ pegar sinônimo de verdade.)
"""
import os
import json
import unicodedata
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

LIB = Path(os.environ.get("DATA_DIR", "./data")) / "library"
_CACHE = {}


def _norm(s: str) -> str:
    s = (s or "").lower()
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def carregar(person: str = None) -> list:
    vids = []
    if not LIB.exists():
        return vids
    for f in LIB.glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        for v in d.get("videos", []):
            v["channel"] = d.get("name")
            v["person"] = d.get("person")
            if person and v["person"] != person:
                continue
            vids.append(v)
    return vids


def _modelo(person: str = None):
    key = person or "all"
    if key in _CACHE:
        return _CACHE[key]
    vids = carregar(person)
    docs = [
        _norm((v.get("title", "") + " ") * 3 + v.get("description", "") + " " + " ".join(v.get("tags", [])))
        for v in vids
    ]
    if not docs:
        _CACHE[key] = ([], None, None)
        return _CACHE[key]
    vec = TfidfVectorizer(ngram_range=(1, 2), min_df=1, max_features=20000)
    mat = vec.fit_transform(docs)
    _CACHE[key] = (vids, vec, mat)
    return _CACHE[key]


def buscar(query: str, person: str = None, top: int = 10) -> list:
    """Retorna [(similaridade, video), ...] ordenado por relevância."""
    vids, vec, mat = _modelo(person)
    if not vids or mat is None:
        return []
    q = vec.transform([_norm(query)])
    sims = cosine_similarity(q, mat)[0]
    ordem = sims.argsort()[::-1][:top]
    return [(round(float(sims[i]), 3), vids[i]) for i in ordem if sims[i] > 0]


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) or "creatina hipertrofia"
    for s, v in buscar(q, top=8):
        print(f"[{s:.2f}] {v.get('views',0):>10,} views — {v['title'][:70]}")
