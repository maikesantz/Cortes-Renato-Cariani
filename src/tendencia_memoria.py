"""Memória de tendência — lê o histórico diário de temas e separa o que CONSOLIDA
do que foi modinha de 1 dia. Grátis: só acumula os JSONs que o trends.py já salva.

Quanto mais dias rodando, mais útil (detecta sazonalidade e sustentação real).
Rodar: python3 src/tendencia_memoria.py
"""
import os
import json
import glob
import datetime
import unicodedata
from pathlib import Path
from collections import defaultdict

DATA = Path(os.environ.get("DATA_DIR", "./data")) / "temas"


def _norm(s: str) -> str:
    s = (s or "").lower()
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).strip()


def historico():
    arquivos = sorted(glob.glob(str(DATA / "20[0-9][0-9]-[0-9][0-9]-[0-9][0-9].json")))
    aparicoes, rotulo = defaultdict(list), {}
    for f in arquivos:
        data = Path(f).stem
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8"))
        except Exception:
            continue
        for t in d.get("temas_em_alta", []):
            k = _norm(t.get("tema", ""))
            if not k:
                continue
            aparicoes[k].append(data)
            rotulo[k] = t["tema"]

    hoje = datetime.date.today().strftime("%Y-%m-%d")
    consolidando, novos, sumindo = [], [], []
    for k, datas in aparicoes.items():
        datas = sorted(set(datas))
        n = len(datas)
        if datas[-1] == hoje:
            (consolidando if n >= 2 else novos).append((rotulo[k], n, datas[0]))
        else:
            sumindo.append((rotulo[k], n, datas[-1]))
    consolidando.sort(key=lambda x: -x[1])
    return arquivos, consolidando, novos, sumindo


def relatorio():
    arqs, consolidando, novos, sumindo = historico()
    print(f"# Memória de tendência ({len(arqs)} dia(s) de histórico)\n")
    if len(arqs) <= 1:
        print("_Só 1 dia coletado até agora. Rode o trends todo dia — a partir de ~1 semana isto"
              " mostra o que sustenta vs o que foi modinha._\n")
    print("## 🔥 Consolidando (aparece em vários dias — aposta segura)")
    print("\n".join(f"- {t} — {n} dias (desde {ini})" for t, n, ini in consolidando) or "- (nenhum ainda)")
    print("\n## 🆕 Novo hoje (vigiar se sustenta)")
    print("\n".join(f"- {t}" for t, _, _ in novos) or "- (nenhum)")
    print("\n## 💨 Esfriando (estava em alta, sumiu hoje)")
    print("\n".join(f"- {t} (visto por último em {ult})" for t, _, ult in sumindo) or "- (nenhum)")


if __name__ == "__main__":
    relatorio()
