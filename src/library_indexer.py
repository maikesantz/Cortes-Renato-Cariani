"""Indexador da biblioteca de vídeos.

Pega TODOS os vídeos públicos de um canal e salva metadados (título, descrição,
duração, views, likes, data) em data/library/<channel>.json.

Não custa nada — só usa YouTube Data API v3 (free tier: 10.000 unidades/dia).
Um canal de ~7.000 vídeos consome ~7.000 unidades — cabe em 1 dia.

Uso:
    python src/library_indexer.py renato_main
    python src/library_indexer.py cariani_tv
    python src/library_indexer.py tati_main
    python src/library_indexer.py all  # roda os 3
"""

import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from googleapiclient.discovery import build

load_dotenv()

DATA_DIR = Path(os.environ.get("DATA_DIR", "./data")) / "library"

# Canais do ecossistema Cariani
CHANNELS = {
    "renato_main": {
        "handle": "@renatocariani",
        "person": "renato",
        "name": "Renato Cariani (canal principal)"
    },
    "cariani_tv": {
        "handle": "@CarianiTV",
        "person": "renato",
        "name": "CarianiTV (cortes + IRONCAST)"
    },
    "renato_cortes": {
        "handle": "@renatocarianicortesyt",
        "person": "renato",
        "name": "Renato Cariani Cortes (RCC)"
    },
    "tati_main": {
        "handle": "@taticariani_",
        "person": "tati",
        "name": "Tati Cariani"
    },
    "julio_main": {
        "handle": "@juliobalestrinoficial",
        "person": "julio",
        "name": "Júlio Balestrin"
    }
}


def get_channel_id(yt, handle: str) -> str:
    """Resolve um handle (@usuario) em channelId — com verificação pra não pegar o canal errado."""
    h = handle.lstrip("@").lower()
    resp = yt.channels().list(part="id", forHandle=h).execute()
    if resp.get("items"):
        return resp["items"][0]["id"]
    # fallback VERIFICADO: só aceita se o customUrl do canal bate com o handle pedido
    resp = yt.search().list(part="snippet", q=handle, type="channel", maxResults=5).execute()
    for it in resp.get("items", []):
        cid = it["snippet"]["channelId"]
        det = yt.channels().list(part="snippet", id=cid).execute()
        custom = det["items"][0]["snippet"].get("customUrl", "").lstrip("@").lower()
        if custom == h:
            return cid
    raise ValueError(
        f"Handle '{handle}' não resolveu para um canal YouTube confiável "
        f"(forHandle vazio e nenhum resultado de busca confirma o handle). "
        f"Revise o handle/URL real do canal em CHANNELS."
    )


def get_uploads_playlist(yt, channel_id: str) -> str:
    """Pega o playlistId de uploads (todos os vídeos do canal)."""
    resp = yt.channels().list(part="contentDetails", id=channel_id).execute()
    return resp["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]


def listar_video_ids(yt, uploads_playlist: str):
    """Itera por todos os vídeos do canal (paginado)."""
    page_token = None
    while True:
        resp = yt.playlistItems().list(
            part="contentDetails",
            playlistId=uploads_playlist,
            maxResults=50,
            pageToken=page_token
        ).execute()

        for item in resp.get("items", []):
            yield item["contentDetails"]["videoId"]

        page_token = resp.get("nextPageToken")
        if not page_token:
            break


def carregar_metadados_em_lote(yt, video_ids: list) -> list:
    """Carrega metadados de até 50 vídeos por vez (limite da API)."""
    resultados = []
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i+50]
        resp = yt.videos().list(
            part="snippet,contentDetails,statistics",
            id=",".join(batch)
        ).execute()
        for item in resp.get("items", []):
            resultados.append({
                "video_id": item["id"],
                "title": item["snippet"]["title"],
                "description": item["snippet"]["description"][:1000],
                "published_at": item["snippet"]["publishedAt"],
                "duration_iso": item["contentDetails"]["duration"],
                "views": int(item["statistics"].get("viewCount", 0)),
                "likes": int(item["statistics"].get("likeCount", 0)),
                "comments": int(item["statistics"].get("commentCount", 0)),
                "thumb": item["snippet"]["thumbnails"].get("high", {}).get("url"),
                "tags": item["snippet"].get("tags", [])
            })
    return resultados


def indexar_canal(channel_key: str, incremental: bool = False, limite: int = None) -> dict:
    """Indexa um canal. incremental=só novos; limite=só os N mais recentes (demo/rápido)."""
    if channel_key not in CHANNELS:
        raise ValueError(f"Canal desconhecido: {channel_key}. Use um dos: {list(CHANNELS.keys())}")

    cfg = CHANNELS[channel_key]
    yt = build("youtube", "v3", developerKey=os.environ["YOUTUBE_API_KEY"])

    # carrega índice existente se for incremental
    existente = None
    ids_conhecidos = set()
    out_path = DATA_DIR / f"{channel_key}.json"
    if incremental and out_path.exists():
        existente = json.loads(out_path.read_text(encoding="utf-8"))
        ids_conhecidos = {v["video_id"] for v in existente.get("videos", [])}
        print(f"[incremental] Índice existente: {len(ids_conhecidos)} vídeos.")

    print(f"[1/4] Resolvendo handle {cfg['handle']}...")
    channel_id = (existente or {}).get("channel_id") or get_channel_id(yt, cfg["handle"])
    print(f"      Channel ID: {channel_id}")

    print(f"[2/4] Buscando playlist de uploads...")
    uploads = get_uploads_playlist(yt, channel_id)

    print(f"[3/4] Listando IDs de vídeos...")
    todos_ids = []
    for vid in listar_video_ids(yt, uploads):
        # se incremental, para quando achar um que já conhece (vídeos vêm ordenados por data)
        if incremental and vid in ids_conhecidos:
            break
        todos_ids.append(vid)
        if limite and len(todos_ids) >= limite:
            break

    if not todos_ids:
        print(f"      Nenhum vídeo novo. Índice já está em dia.")
        return existente

    novos_count = len(todos_ids)
    print(f"      {novos_count} vídeo{'s novos' if incremental else 's'} encontrados.")

    print(f"[4/4] Baixando metadados em lote...")
    novos_videos = carregar_metadados_em_lote(yt, todos_ids)
    print(f"      {len(novos_videos)} metadados carregados.")

    # combina novos + antigos se incremental (dedup por video_id, evita duplicar republicados)
    if incremental and existente:
        vistos = {v["video_id"] for v in novos_videos}
        videos_finais = novos_videos + [v for v in existente["videos"] if v["video_id"] not in vistos]
    else:
        videos_finais = novos_videos

    indice = {
        "channel_key": channel_key,
        "channel_id": channel_id,
        "handle": cfg["handle"],
        "person": cfg["person"],
        "name": cfg["name"],
        "indexed_at": datetime.utcnow().isoformat() + "Z",
        "total_videos": len(videos_finais),
        "videos": sorted(videos_finais, key=lambda v: v["published_at"], reverse=True)
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(indice, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✓ Pronto. {len(videos_finais)} vídeos totais em {out_path}")

    # estatística rápida
    top = sorted(novos_videos, key=lambda v: v["views"], reverse=True)[:5]
    if top:
        print(f"\nTop {len(top)} vídeos {'novos ' if incremental else ''}por views:")
        for v in top:
            print(f"  • {v['views']:>12,} views — {v['title'][:80]}")

    return indice


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python src/library_indexer.py <channel_key>")
        print("\nCanais disponíveis:")
        for k, v in CHANNELS.items():
            print(f"  {k:20s} — {v['name']}")
        print("\nOu use 'all' pra indexar todos.")
        sys.exit(1)

    incremental = "--incremental" in sys.argv
    limite = None
    for a in sys.argv:
        if a.startswith("--limit="):
            limite = int(a.split("=", 1)[1])
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    if args[0] == "all":
        for k in CHANNELS:
            print(f"\n{'='*60}\n  {'Atualizando' if incremental else 'Indexando'}: {CHANNELS[k]['name']}\n{'='*60}")
            try:
                indexar_canal(k, incremental=incremental, limite=limite)
                time.sleep(2)
            except Exception as e:
                print(f"  ✗ Erro: {e}")
    else:
        indexar_canal(args[0], incremental=incremental, limite=limite)
