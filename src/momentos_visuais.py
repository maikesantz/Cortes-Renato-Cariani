"""Detector de momento visual — corte pelo que é MOSTRADO, não só pelo que é falado.

Amostra frames do vídeo e a visão do Claude flaga os momentos visualmente fortes (reação,
expressão de pico, gesto, gag) com timestamp. Complementa o corte por transcrição: pega o ouro
que não tem fala marcante (a cara de espanto, a piada visual — tipo a Filó da Tati).

Custo: usa visão do Claude. Por isso é AMOSTRADO e limitado (intervalo + teto de frames).
Otimização futura: pré-filtrar por movimento/corte de cena (OpenCV, grátis) antes da visão.

Uso:
    python3 src/momentos_visuais.py <video.mp4> [--intervalo 20] [--max 24]
"""
import os
import sys
import json
import base64
import argparse
import subprocess
import tempfile
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def _dur(v):
    out = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                          "-of", "csv=p=0", v], capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def amostrar(video, intervalo=20, maxf=24):
    dur = _dur(video)
    tmp = Path(tempfile.mkdtemp(prefix="mv_"))
    frames = []
    t = 0
    while t < dur and len(frames) < maxf:
        out = tmp / f"f{t}.jpg"
        subprocess.run(["ffmpeg", "-y", "-ss", str(t), "-i", video, "-frames:v", "1",
                        "-vf", "scale=400:-1", "-q:v", "5", str(out)], capture_output=True)
        if out.exists():
            frames.append((t, str(out)))
        t += intervalo
    return frames


def _fmt(t):
    t = int(t)
    return f"{t//3600:02d}:{(t%3600)//60:02d}:{t%60:02d}"


def avaliar(frames, person="renato"):
    from anthropic import Anthropic
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
    flagged = []
    for i in range(0, len(frames), 6):
        bloco = frames[i:i+6]
        content = [{"type": "text", "text":
                    f"São frames de um vídeo do {person.title()}. Flague SÓ os que têm um MOMENTO VISUAL "
                    "forte pra corte: reação/expressão de pico, gesto marcante, piada visual, algo "
                    "que prende mesmo sem áudio. Ignore frame parado/sem graça. Responda APENAS JSON "
                    "[{\"t\": <segundos>, \"motivo\": \"...\"}] (só os bons; pode ser lista vazia)."}]
        for t, f in bloco:
            content.append({"type": "text", "text": f"t={t}s:"})
            content.append({"type": "image", "source": {"type": "base64",
                            "media_type": "image/jpeg", "data": base64.b64encode(Path(f).read_bytes()).decode()}})
        msg = client.messages.create(model=model, max_tokens=500, messages=[{"role": "user", "content": content}])
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            partes = raw.split("```"); raw = partes[1] if len(partes) > 1 else raw.lstrip("`")
            if raw.startswith("json"): raw = raw[4:]
            raw = raw.strip()
        try:
            flagged += json.loads(raw)
        except Exception:
            pass
    return flagged


def rodar(video, intervalo=20, maxf=24):
    frames = amostrar(video, intervalo, maxf)
    print(f"amostrei {len(frames)} frames (a cada {intervalo}s)...")
    momentos = avaliar(frames)
    if not momentos:
        print("Nenhum momento visual forte flagado nesta amostra.")
        return
    print(f"\n## Momentos visuais fortes ({len(momentos)}):")
    for m in sorted(momentos, key=lambda x: x.get("t", 0)):
        print(f"  {_fmt(m.get('t',0))} — {m.get('motivo','')}")
    print("\nCruze com a transcrição pra decidir o recorte; alguns viram corte só pela imagem.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("video")
    p.add_argument("--intervalo", type=int, default=20)
    p.add_argument("--max", type=int, default=24)
    a = p.parse_args()
    rodar(a.video, a.intervalo, a.max)
