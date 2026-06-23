"""Pré-corte — gera o MP4 já cortado de um trecho, pronto pra finalizar (CutPro).

Usa o yt-dlp pra baixar SÓ o pedaço do vídeo (--download-sections), então funciona até
em live de horas sem baixar tudo. Corte preciso nos keyframes.

Uso:
    from precorte import precortar
    precortar("VIDEOID", 159.0, 174.0)   # -> data/clipes/VIDEOID_159-174.mp4
"""
import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
DATA = Path(os.environ.get("DATA_DIR", "./data"))
CLIPES = DATA / "clipes"


def precortar(video_id: str, start: float, end: float, margem: float = 0.4, out: str = None) -> str:
    CLIPES.mkdir(parents=True, exist_ok=True)
    s = max(0.0, float(start) - margem)
    e = float(end) + margem
    out = out or str(CLIPES / f"{video_id}_{int(start)}-{int(end)}.mp4")
    if os.path.exists(out):
        return out
    url = f"https://www.youtube.com/watch?v={video_id}"
    subprocess.run(
        ["yt-dlp", "-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
         "--download-sections", f"*{s}-{e}", "--force-keyframes-at-cuts",
         "--merge-output-format", "mp4", "-o", out, "--no-warnings", url],
        check=True, capture_output=True, text=True
    )
    return out


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("Uso: python precorte.py <video_id> <start_seg> <end_seg>")
        sys.exit(1)
    p = precortar(sys.argv[1], float(sys.argv[2]), float(sys.argv[3]))
    print("clipe:", p, "(%.1f KB)" % (os.path.getsize(p) / 1024))
