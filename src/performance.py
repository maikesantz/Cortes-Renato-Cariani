"""Aprendizado de performance — o que performa de verdade vira PESO no scoring.

Lê os cortes publicados (publicacoes.py) + métricas reais, e calcula, por característica
(pilar, tipo, duração, falante, ter bordão), quanto cada uma rende vs a mediana. Gera
data/feedback/pesos_performance.json — que o scoring usa pra priorizar o que o algoritmo
já provou que funciona. Fecha o loop: o sistema deixa de adivinhar e passa a saber.

Rodar: python3 src/performance.py            # relatório + gera os pesos
       (no scoring) from performance import ajuste -> multiplica a oportunidade do corte
"""
import os
import json
import statistics
from collections import defaultdict
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
DATA = Path(os.environ.get("DATA_DIR", "./data"))
FB = DATA / "feedback"
PUB = FB / "publicados.jsonl"
PESOS = FB / "pesos_performance.json"

MIN_AMOSTRA = 8     # menos que isso = não confia ainda
MIN_POR_GRUPO = 3   # mínimo por categoria pra ter peso


def _banda_dur(d):
    d = d or 0
    return "<12s" if d < 12 else "12-30s" if d < 30 else "30-60s" if d < 60 else "60s+"


def _banda_score(s):
    s = s or 0
    return "8+" if s >= 8 else "7-8" if s >= 7 else "6-7"


def _feature(r, dim):
    f = r.get("features", {})
    if dim == "banda_duracao":
        return _banda_dur(f.get("duracao"))
    if dim == "banda_score":
        return _banda_score(f.get("score"))
    if dim == "tem_bordao":
        return "com_bordao" if f.get("tem_bordao") else "sem_bordao"
    return f.get(dim)


DIMS = ["pilar", "tipo", "falante", "banda_duracao", "banda_score", "tem_bordao"]


def _registros(metrica="views"):
    if not PUB.exists():
        return []
    out = []
    for l in open(PUB, encoding="utf-8"):
        if not l.strip():
            continue
        r = json.loads(l)
        if r.get("metricas", {}).get(metrica) is not None:
            out.append(r)
    return out


def calcular(metrica="views"):
    recs = _registros(metrica)
    if len(recs) < MIN_AMOSTRA:
        return None, len(recs)
    valores = [r["metricas"][metrica] for r in recs]
    mediana = statistics.median(valores) or 1
    pesos = {}
    for dim in DIMS:
        grupos = defaultdict(list)
        for r in recs:
            v = _feature(r, dim)
            if v is not None:
                grupos[v].append(r["metricas"][metrica])
        d = {}
        for val, vals in grupos.items():
            if len(vals) >= MIN_POR_GRUPO:
                d[val] = round(statistics.mean(vals) / mediana, 2)
        if d:
            pesos[dim] = d
    FB.mkdir(parents=True, exist_ok=True)
    PESOS.write_text(json.dumps({"metrica": metrica, "n": len(recs), "pesos": pesos},
                                ensure_ascii=False, indent=2), encoding="utf-8")
    return pesos, len(recs)


def ajuste(cut, dampen=0.5):
    """Multiplicador de performance pro corte (1.0 = neutro). Suave: usa expoente p/ não exagerar."""
    if not PESOS.exists():
        return 1.0
    pesos = json.loads(PESOS.read_text(encoding="utf-8")).get("pesos", {})
    r = {"features": {"pilar": cut.get("pilar_primario"), "tipo": cut.get("tipo_corte"),
                      "falante": cut.get("falante_voz") or cut.get("person"),
                      "duracao": cut.get("duration_seconds"), "score": cut.get("score"),
                      "tem_bordao": bool(cut.get("bordao_presente"))}}
    fator = 1.0
    for dim in DIMS:
        v = _feature(r, dim)
        p = pesos.get(dim, {}).get(v)
        if p:
            fator *= p ** dampen
    return round(fator, 2)


def relatorio():
    pesos, n = calcular()
    if pesos is None:
        print(f"Loop de performance: só {n} cortes publicados com métrica (precisa de {MIN_AMOSTRA}+).")
        print("Registre publicações com publicacoes.py e rode 'atualizar' pra puxar as métricas.")
        return
    print(f"# O que está performando (base: {n} cortes publicados, por views)\n")
    for dim, d in pesos.items():
        ordenado = sorted(d.items(), key=lambda x: -x[1])
        linha = "  ".join(f"{k}={v}x" for k, v in ordenado)
        print(f"  {dim:14}: {linha}")
    print("\nLeitura: valor >1.0 rende acima da mediana; <1.0 abaixo. Esses pesos já entram no scoring.")
    print(f"[pesos salvos em {PESOS}]")


if __name__ == "__main__":
    relatorio()
