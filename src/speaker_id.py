"""Identificação de falante por VOZ (voiceprint), não por texto.

Fluxo:
  - `enroll(nome, audio)` cria a impressão de voz de uma pessoa em data/voices/<nome>.npy
  - `identificar(audio, start, end, voiceprints)` diz quem fala num trecho, por similaridade acústica.

Depende de: resemblyzer + torch (CPU). Se não estiver instalado, o pipeline ignora a etapa.
Instalar: pip install resemblyzer torch
"""
import os
import glob
import tempfile
import subprocess
import warnings
warnings.filterwarnings("ignore")
import numpy as np

VOICES_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "voices")
LIMIAR = 0.72   # acima disso = mesma pessoa (calibrar com mais amostras reais)

_ENCODER = None


def _encoder():
    global _ENCODER
    if _ENCODER is None:
        from resemblyzer import VoiceEncoder
        _ENCODER = VoiceEncoder(verbose=False)
    return _ENCODER


def _embed_arquivo(path):
    from resemblyzer import preprocess_wav
    return _encoder().embed_utterance(preprocess_wav(path))


def enroll(nome: str, audio_path: str) -> str:
    """Cria/atualiza a impressão de voz de uma pessoa."""
    emb = _embed_arquivo(audio_path)
    os.makedirs(VOICES_DIR, exist_ok=True)
    destino = os.path.join(VOICES_DIR, f"{nome}.npy")
    np.save(destino, emb)
    return destino


def carregar_voiceprints() -> dict:
    """Carrega todas as vozes cadastradas: {nome: embedding}."""
    vps = {}
    for f in glob.glob(os.path.join(VOICES_DIR, "*.npy")):
        vps[os.path.splitext(os.path.basename(f))[0]] = np.load(f)
    return vps


def _embed_trecho(audio_path, start, dur):
    fd, tmp = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    subprocess.run(["ffmpeg", "-y", "-i", audio_path, "-ss", str(start), "-t", str(dur), tmp],
                   capture_output=True, check=True)
    try:
        return _embed_arquivo(tmp)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def identificar(audio_path, start, end, voiceprints, limiar=LIMIAR):
    """Retorna (nome, similaridade). 'não identificado' se nenhuma voz bate."""
    if not voiceprints:
        return ("sem_referencia", 0.0)
    dur = max(4, float(end) - float(start))
    try:
        emb = _embed_trecho(audio_path, start, dur)
    except Exception:
        return ("erro_audio", 0.0)
    sims = {n: float(np.dot(emb, v)) for n, v in voiceprints.items()}
    nome, sim = max(sims.items(), key=lambda kv: kv[1])
    return (nome, round(sim, 2)) if sim >= limiar else ("não identificado", round(sim, 2))


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 4 and sys.argv[1] == "enroll":
        print("Cadastrado:", enroll(sys.argv[2], sys.argv[3]))
    else:
        print("Uso: python speaker_id.py enroll <nome> <audio.mp3>")
