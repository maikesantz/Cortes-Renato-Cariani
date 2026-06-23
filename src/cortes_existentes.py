"""Cortes já existentes — usa os canais de CORTES (CarianiTV, RCC) como sinal.

Duas utilidades:
  1) DEDUP: antes de cortar um tema, ver se o time JÁ cortou isso (evita repetir).
  2) ESTILO/PROVA: ver como o time já tratou o tema (o que vira corte, qual gancho usam) +
     as views (o que performou).

É a curadoria humana do que vale corte — vira referência grátis.
Rodar: python3 src/cortes_existentes.py "creatina"
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
CANAIS_CORTES = {"cariani_tv", "renato_cortes"}
_CACHE = None


def _norm(s):
    s = (s or "").lower()
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _modelo():
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    vids = []
    for f in LIB.glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("channel_key") in CANAIS_CORTES:
            for v in d.get("videos", []):
                v["channel"] = d.get("name"); vids.append(v)
    if not vids:
        _CACHE = ([], None, None); return _CACHE
    docs = [_norm(v.get("title", "") + " " + " ".join(v.get("tags", []))) for v in vids]
    vec = TfidfVectorizer(ngram_range=(1, 2))
    mat = vec.fit_transform(docs)
    _CACHE = (vids, vec, mat)
    return _CACHE


def ja_cortado(query, top=5, min_sim=0.12):
    vids, vec, mat = _modelo()
    if not vids or mat is None:
        return []
    q = vec.transform([_norm(query)])
    sims = cosine_similarity(q, mat)[0]
    ordem = sims.argsort()[::-1][:top]
    return [(round(float(sims[i]), 2), vids[i]) for i in ordem if sims[i] >= min_sim]


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) or "creatina"
    res = ja_cortado(q)
    if not res:
        print(f"O time ainda NÃO cortou nada parecido com '{q}'. Pode ser oportunidade nova.")
    else:
        print(f"O time já cortou sobre '{q}' ({len(res)}):")
        for s, v in res:
            print(f"  [{s}] {v.get('views',0):>8,} v · {v['title'][:60]}  ({v['channel']})")
        print("\nUse pra: não repetir o mesmo corte, ou fazer um ângulo diferente do que já existe.")
