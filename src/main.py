"""Pipeline principal — recebe URL do YouTube e roda tudo.

Uso:
    python main.py <url> --person renato
    python main.py <url> --person julio --temas "creatina,treino abc"

Saída:
    Arquivo data/cuts/<video_id>.json com os cortes rankeados
    Adiciona entrada em data/cuts/index.json (fila do dashboard)
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

from download import baixar_audio
from transcribe import transcrever, transcricao_para_texto_com_timestamps
from analyze import analisar
from youtube_meta import metadados
from verify import verificar_e_corrigir

from dotenv import load_dotenv
load_dotenv()

DATA_DIR = Path(os.environ.get("DATA_DIR", "./data"))
CUTS_DIR = DATA_DIR / "cuts"
AUDIO_DIR = DATA_DIR / "audio"
TRANSC_DIR = DATA_DIR / "transcricoes"


def rodar(url: str, person: str, temas: list = None):
    """Roda o pipeline ponta a ponta."""
    CUTS_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    TRANSC_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[1/4] Pegando metadados de {url}...")
    meta = metadados(url)
    video_id = meta["video_id"]
    print(f"      Vídeo: {meta['title']} ({meta['channel']})")

    print(f"[2/4] Baixando áudio...")
    audio_info = baixar_audio(url, str(AUDIO_DIR))
    print(f"      Salvo em: {audio_info['path']} ({audio_info['duration']}s)")

    print(f"[3/4] Transcrevendo via Groq Whisper...")
    transc_path = TRANSC_DIR / f"{video_id}.json"
    if transc_path.exists():
        print(f"      Transcrição já existe, reutilizando.")
        transc = json.loads(transc_path.read_text(encoding="utf-8"))
    else:
        transc = transcrever(audio_info["path"])
        transc_path.write_text(json.dumps(transc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"      {len(transc['segments'])} segments transcritos.")

    print(f"[4/4] Analisando trechos via Claude...")
    texto_ts = transcricao_para_texto_com_timestamps(transc)
    cuts = analisar(
        texto_ts,
        person=person,
        video_id=video_id,
        video_title=meta["title"],
        temas_alta=temas or []
    )

    # verificador: corrige fronteira/timestamp, funde fragmentos, descarta invenção
    aprovados, rejeitados = verificar_e_corrigir(cuts.get("cuts", []), transc["segments"])
    cuts["cuts"] = aprovados
    cuts["rejeitados"] = rejeitados
    print(f"      Verificador: {len(aprovados)} aprovados, {len(rejeitados)} rejeitados (invenção/sem fronteira)")

    # identificação de falante por VOZ (opcional: precisa de resemblyzer + vozes em data/voices/)
    try:
        from speaker_id import carregar_voiceprints, identificar
        vps = carregar_voiceprints()
        if vps:
            print(f"      Identificando falante por voz ({', '.join(vps)})...")
            for c in cuts["cuts"]:
                nome, sim = identificar(audio_info["path"], c["start_seconds"], c["end_seconds"], vps)
                c["falante_voz"] = nome
                c["falante_sim"] = sim
                if nome not in (person, "sem_referencia", "erro_audio", "não identificado"):
                    c["flag"] = c.get("flag") or "outro_falante"
                    c["alerta_falante"] = f"voz parece de {nome}, não de {person}"
    except ImportError:
        pass  # voz não instalada — segue sem identificação acústica

    # loop de performance: re-prioriza pelo que o algoritmo já provou que rende
    try:
        from performance import ajuste
        for c in cuts["cuts"]:
            c["performance_fator"] = ajuste(c)
            c["prioridade"] = round(c.get("score", 0) * c["performance_fator"], 1)
    except Exception:
        pass

    # enriquece cada corte com info do video
    cuts["video_meta"] = meta
    cuts["audio_duration_seconds"] = audio_info["duration"]
    cuts["processed_at"] = datetime.utcnow().isoformat() + "Z"

    out_path = CUTS_DIR / f"{video_id}.json"
    out_path.write_text(json.dumps(cuts, ensure_ascii=False, indent=2), encoding="utf-8")

    # atualiza index.json
    atualizar_index(cuts, video_id)

    print(f"\n✓ Pronto. {len(cuts['cuts'])} cortes salvos em {out_path}")
    print(f"  Top score: {cuts['cuts'][0]['score'] if cuts['cuts'] else 0}")
    print(f"  Dashboard: abra dashboard.html no navegador")

    return cuts


def atualizar_index(cuts: dict, video_id: str):
    """Atualiza data/cuts/index.json — usado pelo dashboard."""
    idx_path = CUTS_DIR / "index.json"
    if idx_path.exists():
        idx = json.loads(idx_path.read_text(encoding="utf-8"))
    else:
        idx = {"videos": [], "cuts": []}

    # remove entradas anteriores desse video
    idx["videos"] = [v for v in idx["videos"] if v["video_id"] != video_id]
    idx["cuts"] = [c for c in idx["cuts"] if c["video_id"] != video_id]

    # adiciona video
    meta = cuts.get("video_meta", {})
    idx["videos"].append({
        "video_id": video_id,
        "title": meta.get("title", ""),
        "channel": meta.get("channel", ""),
        "person": cuts.get("person", ""),
        "thumb": meta.get("thumb", ""),
        "processed_at": cuts.get("processed_at", ""),
        "total_cuts": len(cuts.get("cuts", []))
    })

    # adiciona cuts com referencia ao video
    for c in cuts.get("cuts", []):
        c2 = dict(c)
        c2["video_id"] = video_id
        c2["video_title"] = meta.get("title", "")
        c2["video_url"] = meta.get("url") or f"https://youtube.com/watch?v={video_id}"
        c2["person"] = cuts.get("person", "")
        c2["status"] = "pending"  # pending | cortado | descartado
        idx["cuts"].append(c2)

    # ordena por score desc
    idx["cuts"].sort(key=lambda x: x.get("score", 0), reverse=True)

    idx["generated_at"] = datetime.utcnow().isoformat() + "Z"
    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")

    # também grava index.js para o dashboard (carregado via <script>, funciona em file:// sem CORS)
    js_path = CUTS_DIR / "index.js"
    js_path.write_text("window.CUTS_INDEX = " + json.dumps(idx, ensure_ascii=False) + ";", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline de cortes Cariani")
    parser.add_argument("url", help="URL do vídeo YouTube")
    parser.add_argument("--person", choices=["renato", "julio", "tati"], required=True,
                        help="Personagem do vídeo (define qual persona aplicar)")
    parser.add_argument("--temas", default="",
                        help="Temas em alta hoje, separados por vírgula")
    args = parser.parse_args()

    temas = [t.strip() for t in args.temas.split(",") if t.strip()]
    rodar(args.url, args.person, temas)
