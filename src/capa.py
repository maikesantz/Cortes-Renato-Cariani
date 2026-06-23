"""Sugestão de frame de CAPA — a primeira pitada de 'visão' no sistema.

Extrai alguns frames do corte e pede pro Claude (visão) escolher o melhor pra capa de Reels:
rosto nítido, expressão de pico, sem boca/olho no meio do movimento. Salva o frame escolhido.

Uso:
    python3 src/capa.py <caminho_do_mp4>
    python3 src/capa.py <video_id> <start_seg> <end_seg>   # pré-corta e escolhe
"""
import os
import sys
import json
import base64
import subprocess
import tempfile
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
DATA = Path(os.environ.get("DATA_DIR", "./data"))


def _dur(mp4):
    out = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                          "-of", "csv=p=0", mp4], capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def extrair_frames(mp4, n=6):
    dur = _dur(mp4) or 10
    tmp = Path(tempfile.mkdtemp(prefix="capa_"))
    frames = []
    for i in range(n):
        t = dur * (i + 0.5) / n
        out = tmp / f"f{i}.jpg"
        subprocess.run(["ffmpeg", "-y", "-ss", str(t), "-i", mp4, "-frames:v", "1",
                        "-vf", "scale=480:-1", "-q:v", "4", str(out)],
                       capture_output=True)
        if out.exists():
            frames.append((round(t, 1), str(out)))
    return frames


def escolher(frames):
    from anthropic import Anthropic
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
    content = [{"type": "text", "text":
                "Escolha o MELHOR frame pra CAPA de um Reels fitness: rosto nítido e bem enquadrado, "
                "expressão forte/de pico, nada de olho fechado ou boca no meio de palavra, boa leitura como "
                "thumbnail. Responda APENAS JSON {\"melhor\": <indice>, \"motivo\": \"...\"}."}]
    for i, (t, f) in enumerate(frames):
        b64 = base64.b64encode(Path(f).read_bytes()).decode()
        content.append({"type": "text", "text": f"Frame {i} (em {t}s):"})
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}})
    msg = client.messages.create(model=model, max_tokens=300, messages=[{"role": "user", "content": content}])
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        partes = raw.split("```"); raw = partes[1] if len(partes) > 1 else raw.lstrip("`")
        if raw.startswith("json"): raw = raw[4:]
        raw = raw.strip()
    return json.loads(raw)


def sugerir(mp4, salvar_em=None):
    frames = extrair_frames(mp4)
    if not frames:
        print("Não consegui extrair frames."); return
    r = escolher(frames)
    idx = r.get("melhor", 0)
    idx = idx if 0 <= idx < len(frames) else 0
    t, src = frames[idx]
    destino = salvar_em or str(Path(mp4).with_suffix("")) + "_capa.jpg"
    subprocess.run(["cp", src, destino], capture_output=True)
    print(f"capa escolhida: frame {idx} (em {t}s) → {destino}")
    print(f"motivo: {r.get('motivo','')}")
    return destino


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) == 3:
        sys.path.insert(0, str(Path(__file__).parent))
        from precorte import precortar
        mp4 = precortar(a[0], float(a[1]), float(a[2]))
        sugerir(mp4)
    elif len(a) == 1:
        sugerir(a[0])
    else:
        print("Uso: python3 src/capa.py <mp4>  |  <video_id> <start> <end>")
