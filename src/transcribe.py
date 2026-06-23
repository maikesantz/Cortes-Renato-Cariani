"""Transcrição via Groq Whisper Large v3 Turbo.

Saída: lista de segments com timestamps + texto.
"""

import os
import json
import glob
import shutil
import tempfile
import subprocess
from pathlib import Path
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# "Dicionário" de nomes/termos do nicho — reduz erro de transcrição (ex.: Muzy, Balestrin)
VOCAB_HINT = ("Renato Cariani, Tati Cariani, Júlio Balestrin, Paulo Muzy, Toguro, IRONCAST, "
              "deltoide, porção lateral, hipertrofia, periodização, fadiga, tensão, anabolizante.")


LIMITE_MB = 24          # acima disso a Groq recusa (limite ~25MB no free tier)
CHUNK_SECONDS = 900     # 15 min por pedaço (~11-15MB, folga segura)


def _duracao(path: str) -> float:
    """Duração real do áudio em segundos (via ffprobe)."""
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        capture_output=True, text=True
    )
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def _transcrever_arquivo(path: str, lang: str) -> tuple:
    """Uma chamada à Groq. Retorna (segments, texto_completo)."""
    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    model = os.environ.get("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")
    with open(path, "rb") as f:
        result = client.audio.transcriptions.create(
            file=(Path(path).name, f.read()),
            model=model,
            language=lang,
            prompt=VOCAB_HINT,
            response_format="verbose_json",
            timestamp_granularities=["segment"]
        )
    segments = [{"start": float(s["start"]), "end": float(s["end"]), "text": s["text"].strip()}
                for s in result.segments]
    return segments, result.text


def transcrever(audio_path: str, lang: str = "pt") -> dict:
    """Transcreve o áudio. Se passar de ~24MB, corta em pedaços e recola os timestamps."""
    size_mb = os.path.getsize(audio_path) / 1024 / 1024

    # Caso simples: cabe numa chamada só
    if size_mb <= LIMITE_MB:
        segments, texto = _transcrever_arquivo(audio_path, lang)
        return {"text_full": texto, "segments": segments, "language": lang,
                "duration": _duracao(audio_path), "chunks": 1}

    # Caso grande: divide em pedaços de CHUNK_SECONDS (sem reencodar = rápido)
    print(f"      Áudio de {size_mb:.0f}MB > {LIMITE_MB}MB — dividindo em pedaços de {CHUNK_SECONDS//60}min...")
    tmp = tempfile.mkdtemp(prefix="cortes_chunks_")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", audio_path, "-f", "segment",
             "-segment_time", str(CHUNK_SECONDS), "-c", "copy",
             os.path.join(tmp, "chunk_%03d.mp3")],
            check=True, capture_output=True
        )
        pedacos = sorted(glob.glob(os.path.join(tmp, "chunk_*.mp3")))
        all_segments, partes_texto, offset = [], [], 0.0
        for i, ch in enumerate(pedacos):
            print(f"      Transcrevendo pedaço {i+1}/{len(pedacos)}...")
            segs, txt = _transcrever_arquivo(ch, lang)
            for s in segs:                                   # desloca pro tempo real do vídeo
                all_segments.append({"start": s["start"] + offset,
                                     "end": s["end"] + offset, "text": s["text"]})
            partes_texto.append(txt)
            offset += _duracao(ch)                           # acumula pela duração REAL (sem drift)
        return {"text_full": " ".join(partes_texto), "segments": all_segments,
                "language": lang, "duration": offset, "chunks": len(pedacos)}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def transcricao_para_texto_com_timestamps(transcricao: dict) -> str:
    """Formata a transcrição como texto numerado com timestamps, pra mandar pro Claude."""
    linhas = []
    for seg in transcricao["segments"]:
        h = int(seg["start"] // 3600)
        m = int((seg["start"] % 3600) // 60)
        s = int(seg["start"] % 60)
        ts = f"{h:02d}:{m:02d}:{s:02d}"
        linhas.append(f"[{ts}] {seg['text']}")
    return "\n".join(linhas)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python transcribe.py <audio.mp3>")
        sys.exit(1)
    out = transcrever(sys.argv[1])
    print(f"Total segments: {len(out['segments'])}")
    print(f"Duração: {out['duration']}s")
    print("Primeiros 3 segments:")
    for s in out["segments"][:3]:
        print(f"  [{s['start']:.1f}s] {s['text']}")
