"""Auto-reframe vertical — transforma o corte 16:9 em 9:16 SEGUINDO o rosto.

Em vez de corte burro no centro (que corta o Renato pela metade), detecta o rosto quadro a
quadro, suaviza o movimento e recorta uma janela 9:16 que acompanha o falante. Depois recola
o áudio original. Pronto pra Reels/TikTok/Shorts.

Depende de opencv-python-headless (pip install opencv-python-headless) + ffmpeg.
Uso:
    python3 src/reframe.py <clipe.mp4>            # -> <clipe>_vertical.mp4
"""
import os
import sys
import subprocess
import tempfile
from pathlib import Path
import cv2

_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")


def _centro_rosto(frame_gray, w):
    faces = _CASCADE.detectMultiScale(frame_gray, scaleFactor=1.2, minNeighbors=5,
                                      minSize=(int(w * 0.06), int(w * 0.06)))
    if len(faces) == 0:
        return None
    # maior rosto (provável o falante em primeiro plano)
    fx, fy, fw, fh = max(faces, key=lambda f: f[2] * f[3])
    return fx + fw / 2


def reframe(clipe, out=None, alpha=0.12):
    cap = cv2.VideoCapture(clipe)
    if not cap.isOpened():
        print("não abri o clipe"); return
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    crop_w = min(W, int(round(H * 9 / 16)))   # janela 9:16 mantendo a altura
    cx = W / 2                                  # centro suavizado (EMA)
    half = crop_w / 2

    tmp = tempfile.mktemp(suffix=".mp4")
    vw = cv2.VideoWriter(tmp, cv2.VideoWriter_fourcc(*"mp4v"), fps, (1080, 1920))
    i = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i % 3 == 0:   # detecta a cada 3 frames (rápido); suaviza no meio
            gray = cv2.cvtColor(cv2.resize(frame, (W // 2, H // 2)), cv2.COLOR_BGR2GRAY)
            c = _centro_rosto(gray, W // 2)
            if c is not None:
                cx = (1 - alpha) * cx + alpha * (c * 2)   # volta pra escala original
        cx = max(half, min(W - half, cx))
        x0 = int(cx - half)
        recorte = frame[:, x0:x0 + crop_w]
        vw.write(cv2.resize(recorte, (1080, 1920)))
        i += 1
    cap.release(); vw.release()

    out = out or str(Path(clipe).with_suffix("")) + "_vertical.mp4"
    # recola o áudio original
    subprocess.run(["ffmpeg", "-y", "-i", tmp, "-i", clipe, "-map", "0:v", "-map", "1:a?",
                    "-c:v", "libx264", "-c:a", "aac", "-shortest", out], capture_output=True)
    if os.path.exists(tmp):
        os.remove(tmp)
    print(f"vertical (9:16, seguindo o rosto): {out}  ({i} frames)")
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 src/reframe.py <clipe.mp4>"); sys.exit(1)
    reframe(sys.argv[1])
