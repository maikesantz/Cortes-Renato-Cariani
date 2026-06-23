"""Lista as lives / vídeos longos do acervo — onde está o conteúdo multi-tema.

A busca por título não pega o que é falado dentro de uma live de horas. Pra desbloquear esse
conteúdo, é preciso TRANSCREVER a live (roda no pipeline; o chunking aguenta horas). Depois,
`busca_transcricao.py` acha qualquer tema lá dentro com timestamp.

Aqui a gente lista as lives ordenadas por views (mais assistidas = mais potencial de corte),
já com o comando pronto e uma estimativa de custo de transcrição.

Rodar: python3 src/lives.py            (lives de >1h)
       python3 src/lives.py 2          (só de >2h)
"""
import os
import re
import json
import glob
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
LIB = Path(os.environ.get("DATA_DIR", "./data")) / "library"


def _secs(iso: str) -> int:
    h = re.search(r"(\d+)H", iso); m = re.search(r"(\d+)M", iso); s = re.search(r"(\d+)S", iso)
    return (int(h.group(1)) * 3600 if h else 0) + (int(m.group(1)) * 60 if m else 0) + (int(s.group(1)) if s else 0)


def listar(min_horas: float = 1.0):
    vids = []
    for f in glob.glob(str(LIB / "*.json")):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        person = d.get("person", "")
        for v in d.get("videos", []):
            dur = _secs(v.get("duration_iso", ""))
            if dur >= min_horas * 3600:
                v["_dur"] = dur; v["_person"] = person
                vids.append(v)
    vids.sort(key=lambda x: x.get("views", 0), reverse=True)
    return vids


def relatorio(min_horas: float = 1.0):
    vids = listar(min_horas)
    horas_total = sum(v["_dur"] for v in vids) / 3600
    custo = horas_total * 0.04 * 5.4  # Groq US$0.04/h -> R$
    print(f"# Lives / vídeos longos (>{min_horas:g}h) — candidatos a transcrever\n")
    print(f"Total: {len(vids)} vídeos · {horas_total:.0f}h de conteúdo · "
          f"transcrever tudo ≈ R$ {custo:.0f} (uma vez)\n")
    print("Mais assistidos primeiro (maior potencial de corte):\n")
    for v in vids[:15]:
        h, m = v["_dur"] // 3600, (v["_dur"] % 3600) // 60
        print(f"  {h}h{m:02d}m · {v.get('views',0):>10,} v · {v['title'][:52]}")
        print(f"     python3 src/main.py \"https://youtube.com/watch?v={v['video_id']}\" --person {v['_person']}")
    if len(vids) > 15:
        print(f"\n  … e mais {len(vids)-15}. Depois de transcrever, use:")
        print("     python3 src/busca_transcricao.py \"tema que você quer achar\"")


if __name__ == "__main__":
    import sys
    relatorio(float(sys.argv[1]) if len(sys.argv) > 1 else 1.0)
