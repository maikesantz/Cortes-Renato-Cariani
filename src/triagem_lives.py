"""Triagem das lives — separa CONTEÚDO (tem corte) de ENTRETENIMENTO (viagem/zoeira).

Nem toda live longa vale transcrever: "Expedição Paraguai" não tem corte técnico.
Aqui a gente classifica pelos títulos e mostra o custo SÓ do que rende corte.

Rodar:
    python3 src/triagem_lives.py            # heurística (grátis, instantânea)
    python3 src/triagem_lives.py --ia       # classifica com Claude (mais preciso, ~R$0,10)
"""
import os
import re
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
LIB = Path(os.environ.get("DATA_DIR", "./data")) / "library"
USD_H, BRL = 0.04, 5.4

CONTEUDO_KW = ["treino dos caras", "[irl]", "ironcast", "responde", "tira-duvida", "tira duvida",
               "perguntas", "como ", "dieta", "tecnica", "técnica", "explica", "ciencia", "ciência",
               "treino de", "hipertrofia", "nutri", "suplement", "live de treino", "aula", "q&a"]
ENTRET_KW = ["expedicao", "expedição", "garagem", "viagem", "invadi", "invadimos", "bebado", "bêbado",
             "paraguai", "transamazonica", "transamazônica", "aventura", "porsche", "mansao", "mansão",
             "safari", "role", "rolê", "dia 0", "dia 1", "dia 2", "show pro", "ao vivo direto", "carro",
             "milhoes", "milhões", "praia", "lancha", "jet", "passeio", "churrasco", "festa"]


def _secs(iso):
    h = re.search(r"(\d+)H", iso); m = re.search(r"(\d+)M", iso); s = re.search(r"(\d+)S", iso)
    return (int(h.group(1)) * 3600 if h else 0) + (int(m.group(1)) * 60 if m else 0) + (int(s.group(1)) if s else 0)


def _norm(s):
    return (s or "").lower()


def lives(min_h=1.0):
    out = []
    for f in LIB.glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        for v in d.get("videos", []):
            if _secs(v.get("duration_iso", "")) >= min_h * 3600:
                v["_dur"] = _secs(v["duration_iso"]); v["_person"] = d.get("person")
                out.append(v)
    return out


def classificar_heuristica(vs):
    lab = {}
    for v in vs:
        t = _norm(v["title"])
        c = sum(1 for k in CONTEUDO_KW if k in t)
        e = sum(1 for k in ENTRET_KW if k in t)
        lab[v["video_id"]] = "conteudo" if c >= e and c > 0 else ("entretenimento" if e > 0 else "incerto")
    return lab


def classificar_ia(vs):
    from anthropic import Anthropic
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
    lista = [{"id": v["video_id"], "t": v["title"][:90]} for v in vs]
    lab = {}
    for i in range(0, len(lista), 100):
        bloco = lista[i:i+100]
        prompt = ("Classifique cada live do Renato Cariani em 'conteudo' ou 'entretenimento':\n"
                  "- conteudo: treino, técnica, nutrição, suplementação, Q&A, IRONCAST, podcast de FALA (tem corte aproveitável).\n"
                  "- entretenimento: viagem, aventura, expedição, zoeira, carro, festa, bastidor sem ensino (sem corte técnico).\n\n"
                  "Responda APENAS um array JSON, um objeto por vídeo:\n"
                  '[{"id":"abc","cat":"conteudo"},{"id":"xyz","cat":"entretenimento"}]\n\n'
                  "Vídeos:\n" + json.dumps(bloco, ensure_ascii=False))
        msg = client.messages.create(model=model, max_tokens=4500, messages=[{"role": "user", "content": prompt}])
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]; raw = raw[4:] if raw.startswith("json") else raw; raw = raw.rsplit("```", 1)[0]
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                data = [{"id": k, "cat": v} for k, v in data.items()]
            for item in data:
                cat = str(item.get("cat", "")).lower()
                lab[item.get("id")] = "conteudo" if "conteud" in cat else ("entretenimento" if "entret" in cat else "incerto")
        except Exception:
            pass
    return lab


def relatorio(min_h=1.0, usar_ia=False):
    vs = lives(min_h)
    if not vs:
        print("Acervo não indexado (rode library_indexer.py).")
        return
    if usar_ia:
        # teto de segurança: classifica no máx 500 lives por vez (1 chamada Claude / 100)
        alvo = sorted(vs, key=lambda x: x.get("views", 0), reverse=True)[:500]
        print(f"[IA: classificando {len(alvo)} lives em ~{(len(alvo)+99)//100} chamada(s) Claude (~R${(len(alvo)+99)//100*0.05:.2f})]")
        lab = classificar_ia(alvo)
    else:
        lab = classificar_heuristica(vs)
    buckets = {"conteudo": [], "entretenimento": [], "incerto": []}
    for v in vs:
        buckets.get(lab.get(v["video_id"], "incerto"), buckets["incerto"]).append(v)

    print(f"# Triagem de lives (>{min_h:g}h) — {'Claude' if usar_ia else 'heurística'}\n")
    for nome in ("conteudo", "entretenimento", "incerto"):
        b = buckets[nome]
        h = sum(v["_dur"] for v in b) / 3600
        print(f"  {nome.upper():14} {len(b):4} lives · {h:6.0f}h · ~R$ {h*USD_H*BRL:5.0f}")
    nvids = json.load(open(next(LIB.glob('renato_main.json'))))['total_videos'] if (LIB/'renato_main.json').exists() else len(vs)
    print(f"\n[amostra de {len(vs)} lives — projete x(7748/{nvids}) pro canal completo]")

    print("\n## Melhores lives de CONTEÚDO pra transcrever (por views):")
    for v in sorted(buckets["conteudo"], key=lambda x: x.get("views", 0), reverse=True)[:12]:
        print(f"  ~{v['_dur']//3600}h · {v.get('views',0):>10,} v · {v['title'][:50]}")
    if buckets["conteudo"]:
        ids = [v["video_id"] for v in sorted(buckets["conteudo"], key=lambda x: x.get('views',0), reverse=True)]
        (Path(os.environ.get("DATA_DIR","./data"))/"temas"/"lives_conteudo.json").write_text(
            json.dumps(ids, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    import sys
    relatorio(min_h=1.0, usar_ia=("--ia" in sys.argv))
