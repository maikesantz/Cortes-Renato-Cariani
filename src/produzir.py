"""Pacote de produção — transforma os cortes aprovados em entregáveis prontos pro editor/CutPro.

Para cada corte: gera o MP4 já cortado + a legenda SRT + uma ficha com título de capa, copy,
pilar e falante. É só o editor/CutPro pegar e finalizar (reframe, branding, exportar).

Uso:
    python3 src/produzir.py <video_id>            # produz os cortes 'cortado'/pendentes do vídeo
    python3 src/produzir.py <video_id> --top 5    # só os 5 melhores
"""
import os
import sys
import json
import argparse
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
from precorte import precortar
from legendas import gerar_srt

DATA = Path(os.environ.get("DATA_DIR", "./data"))


def _ficha(c, video_id):
    cap = (c.get("headline_post") or c.get("title_sugerido") or "").replace("*", "")
    return (
        f"CAPA: {cap}\n"
        f"TÍTULO: {c.get('title_sugerido','')}\n"
        f"COPY: {c.get('copy_short_sugerida','')}\n"
        f"PILAR: {c.get('pilar_primario','')}  |  TIPO: {c.get('tipo_corte','')}  |  SCORE: {c.get('score','')}\n"
        f"FALANTE (voz): {c.get('falante_voz','?')}  |  FIDELIDADE: {c.get('fidelidade','?')}\n"
        f"TRECHO ({c.get('start_timestamp')}–{c.get('end_timestamp')}): {c.get('transcricao_trecho','')[:400]}\n"
        f"FONTE: https://youtube.com/watch?v={video_id}&t={int(c.get('start_seconds',0))}s\n"
    )


def produzir(video_id, top=None, somente_status=None):
    cuts_path = DATA / "cuts" / f"{video_id}.json"
    if not cuts_path.exists():
        print(f"Sem cortes pra {video_id} (rode o pipeline antes).")
        return
    data = json.loads(cuts_path.read_text(encoding="utf-8"))
    cuts = sorted(data.get("cuts", []), key=lambda x: x.get("score", 0), reverse=True)
    if somente_status:
        cuts = [c for c in cuts if c.get("status", "pending") in somente_status]
    if top:
        cuts = cuts[:top]
    if not cuts:
        print("Nenhum corte pra produzir.")
        return

    destino = DATA / "clipes" / video_id
    destino.mkdir(parents=True, exist_ok=True)
    feitos = 0
    for c in cuts:
        s, e = c.get("start_seconds"), c.get("end_seconds")
        if s is None or e is None or e <= s:
            print(f"  pulei cut {c.get('id')} (sem timestamps válidos)")
            continue
        base = destino / f"cut{c.get('id','x')}_{int(s)}-{int(e)}"
        print(f"  produzindo cut {c.get('id')} [{c.get('start_timestamp')}–{c.get('end_timestamp')}] {c.get('title_sugerido','')[:40]}")
        # 1) ficha + legenda primeiro (instantâneos, não dependem de download)
        (Path(str(base) + ".txt")).write_text(_ficha(c, video_id), encoding="utf-8")
        try:
            gerar_srt(video_id, s, e, out=str(base) + ".srt")
        except FileNotFoundError:
            pass  # sem transcrição cacheada (ok)
        # 2) o MP4 do trecho (parte lenta)
        try:
            precortar(video_id, s, e, out=str(base) + ".mp4")
            feitos += 1
        except Exception as ex:
            print(f"    erro no mp4: {str(ex)[:80]} (ficha+srt já salvos)")
    print(f"\n✓ {feitos} pacote(s) em {destino}/  (mp4 + srt + ficha por corte)")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("video_id")
    p.add_argument("--top", type=int, default=None)
    p.add_argument("--cortados", action="store_true", help="só os marcados 'cortado' no dashboard")
    a = p.parse_args()
    produzir(a.video_id, top=a.top, somente_status=(["cortado"] if a.cortados else None))
