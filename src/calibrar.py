"""Calibração por PERFORMANCE — deriva os pesos do score do que o público já premiou.

Os canais de cortes (CarianiTV, RCC) são um gabarito pronto: cada corte publicado tem views
reais. Em vez de chutar os pesos do score, a gente aprende com o que de fato performou.

Dois níveis:
  - título/tema (grátis): que padrões de título/assunto rendem mais (cita Toguro, caixa alta, etc.).
  - conteúdo (--conteudo N): transcreve uma amostra de bombou-vs-encalhou e o Claude diz o que
    separa um do outro (pilar, bordão, gancho, duração) → recomendações pros pesos.

Uso:
    python3 src/calibrar.py                 # nível título (grátis)
    python3 src/calibrar.py --conteudo 10   # + nível conteúdo (transcreve 10 alto + 10 baixo)
"""
import os
import sys
import json
import statistics
import unicodedata
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
DATA = Path(os.environ.get("DATA_DIR", "./data"))
LIB = DATA / "library"
FB = DATA / "feedback"
CANAIS_CORTES = {"cariani_tv", "renato_cortes"}


def _norm(s):
    s = (s or "").lower()
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _cortes():
    out = []
    for f in LIB.glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("channel_key") in CANAIS_CORTES:
            out += [v for v in d.get("videos", []) if v.get("views")]
    return out


FEATS = {
    "pergunta (?)": lambda t: "?" in t,
    "caixa alta forte": lambda t: sum(1 for w in t.split() if len(w) > 3 and w.isupper()) >= 3,
    "cita Toguro": lambda t: "toguro" in _norm(t),
    "cita Balestrin": lambda t: "balestrin" in _norm(t),
    "tema treino": lambda t: any(k in _norm(t) for k in ["treino", "exercicio", "musculo", "ombro", "peito", "perna", "biceps"]),
    "tema dieta": lambda t: any(k in _norm(t) for k in ["dieta", "comida", "caloria", "proteina", "frango", "carbo"]),
    "polemica/revela": lambda t: any(k in _norm(t) for k in ["exp", "verdade", "revela", "real", "polemic", "barraco", "treta"]),
    "convidado/famoso": lambda t: any(k in _norm(t) for k in ["ramon", "muzy", "richard", "gordox", "rato", "adibe"]),
}


def calibrar_titulo():
    vids = _cortes()
    if len(vids) < 30:
        print("Poucos cortes indexados — rode library_indexer.py cariani_tv (e renato_cortes).")
        return {}
    med = statistics.median(v["views"] for v in vids)
    print(f"# Calibração por performance — título/tema ({len(vids)} cortes, mediana {int(med):,} views)\n")
    pesos = {}
    for nome, fn in FEATS.items():
        com = [v["views"] for v in vids if fn(v["title"])]
        sem = [v["views"] for v in vids if not fn(v["title"])]
        if len(com) >= 8 and sem:
            mult = round(statistics.median(com) / statistics.median(sem), 2)
            pesos[nome] = {"mult": mult, "n": len(com)}
            seta = "↑" if mult >= 1.15 else ("↓" if mult <= 0.85 else "·")
            print(f"  {seta} {nome:20} {mult:.2f}x   ({len(com)} cortes)")
    FB.mkdir(parents=True, exist_ok=True)
    (FB / "calibragem_titulo.json").write_text(json.dumps(pesos, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[salvo em {FB/'calibragem_titulo.json'}]")
    print("Leitura: >1.15 priorize, <0.85 segure. Já dá pra ajustar headline/prioridade por aqui.")
    return pesos


def calibrar_conteudo(n=10):
    vids = sorted(_cortes(), key=lambda v: v["views"], reverse=True)
    vids = [v for v in vids if v["views"] > 0]
    if len(vids) < 2 * n:
        n = len(vids) // 2
    altos = vids[:n]
    baixos = [v for v in vids if v["views"] >= 200][-n:]
    print(f"\n# Calibração por conteúdo — transcrevendo {len(altos)} bombaram + {len(baixos)} encalharam...")
    sys.path.insert(0, str(Path(__file__).parent))
    from download import baixar_audio
    from transcribe import transcrever

    amostra = []
    for faixa, grupo in [("BOMBOU", altos), ("ENCALHOU", baixos)]:
        for v in grupo:
            vid = v["video_id"]
            cache = DATA / "transcricoes" / f"{vid}.json"
            try:
                if cache.exists():
                    t = json.loads(cache.read_text(encoding="utf-8"))
                else:
                    info = baixar_audio(f"https://youtube.com/watch?v={vid}", str(DATA / "audio"))
                    t = transcrever(info["path"])
                    cache.write_text(json.dumps(t, ensure_ascii=False), encoding="utf-8")
                amostra.append({"faixa": faixa, "views": v["views"], "titulo": v["title"][:60],
                                "fala": (t.get("text_full") or "")[:600]})
            except Exception as e:
                print(f"  (pulei {vid}: {str(e)[:50]})")

    if len(amostra) < 6:
        print("Amostra pequena demais pra concluir."); return
    from anthropic import Anthropic
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
    prompt = (
        "Você calibra o critério de corte do Renato Cariani. Abaixo, cortes que BOMBARAM e que "
        "ENCALHARAM (com views reais e a transcrição). Diga o que separa um do outro: tipo de gancho, "
        "presença de bordão, pilar (ciência/disciplina/superação), duração da fala, energia, presença "
        "de convidado/famoso. Termine com 3-5 RECOMENDAÇÕES concretas pros pesos do score "
        "(ex.: 'subir bônus de gancho', 'cortes com Toguro/convidado pesam mais').\n\n"
        f"DADOS:\n{json.dumps(amostra, ensure_ascii=False, indent=1)}"
    )
    msg = client.messages.create(model=model, max_tokens=900, messages=[{"role": "user", "content": prompt}])
    print("\n" + msg.content[0].text.strip())


if __name__ == "__main__":
    calibrar_titulo()
    if "--conteudo" in sys.argv:
        i = sys.argv.index("--conteudo")
        n = int(sys.argv[i + 1]) if i + 1 < len(sys.argv) and sys.argv[i + 1].isdigit() else 10
        calibrar_conteudo(n)
