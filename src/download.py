"""Download de audio do YouTube via yt-dlp.

Uso:
    from download import baixar_audio
    info = baixar_audio("https://youtube.com/watch?v=xxx", "./data")
    # retorna: {"path": "...mp3", "title": "...", "duration": 1234, "video_id": "xxx"}
"""

import os
import subprocess
import json
from pathlib import Path


def baixar_audio(url: str, output_dir: str = "./data") -> dict:
    """Baixa o audio do YouTube em mp3 e retorna metadados."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # extrai video_id pra nomear arquivo
    info_proc = subprocess.run(
        ["yt-dlp", "--dump-json", "--no-warnings", url],
        capture_output=True, text=True, check=True
    )
    info = json.loads(info_proc.stdout)
    video_id = info["id"]
    title = info["title"]
    duration = info["duration"]

    audio_path = Path(output_dir) / f"{video_id}.mp3"

    if not audio_path.exists():
        subprocess.run([
            "yt-dlp",
            "-x", "--audio-format", "mp3",
            "--audio-quality", "5",  # qualidade média (suficiente pra transcrição)
            "-o", str(audio_path).replace(".mp3", ".%(ext)s"),
            "--no-warnings",
            url
        ], check=True)

    return {
        "path": str(audio_path),
        "title": title,
        "duration": duration,
        "video_id": video_id,
        "url": url
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python download.py <url_youtube>")
        sys.exit(1)
    print(json.dumps(baixar_audio(sys.argv[1]), indent=2, ensure_ascii=False))
