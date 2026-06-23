"""Pega metadados do YouTube via Data API v3 (título, descrição, duração, thumb)."""

import os
import re
from dotenv import load_dotenv
from googleapiclient.discovery import build

load_dotenv()


def extrair_video_id(url: str) -> str:
    """Extrai o video ID de qualquer formato de URL do YouTube."""
    patterns = [
        r"youtube\.com/watch\?v=([^&]+)",
        r"youtu\.be/([^?]+)",
        r"youtube\.com/shorts/([^?]+)",
        r"youtube\.com/embed/([^?]+)"
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    raise ValueError(f"Não consegui extrair video ID de: {url}")


def metadados(url_ou_id: str) -> dict:
    """Retorna metadados do vídeo."""
    if url_ou_id.startswith("http"):
        video_id = extrair_video_id(url_ou_id)
    else:
        video_id = url_ou_id

    yt = build("youtube", "v3", developerKey=os.environ["YOUTUBE_API_KEY"])
    resp = yt.videos().list(
        part="snippet,contentDetails,statistics",
        id=video_id
    ).execute()

    if not resp["items"]:
        raise ValueError(f"Vídeo não encontrado: {video_id}")

    item = resp["items"][0]
    return {
        "video_id": video_id,
        "title": item["snippet"]["title"],
        "description": item["snippet"]["description"][:500],
        "channel": item["snippet"]["channelTitle"],
        "published_at": item["snippet"]["publishedAt"],
        "duration_iso": item["contentDetails"]["duration"],
        "views": int(item["statistics"].get("viewCount", 0)),
        "likes": int(item["statistics"].get("likeCount", 0)),
        "thumb": item["snippet"]["thumbnails"].get("high", {}).get("url"),
    }
