"""Processamento em lote — recebe lista de URLs e roda o pipeline em todos.

Uso:
    # Modo arquivo (uma URL por linha):
    python src/batch_process.py videos.txt --person renato

    # Modo stdin (pipe):
    cat videos.txt | python src/batch_process.py - --person julio --temas "creatina,lipedema"

    # Com pausa entre vídeos pra não pesar nas APIs:
    python src/batch_process.py videos.txt --person renato --delay 30

Formato do arquivo (videos.txt):
    https://youtube.com/watch?v=AAAA
    https://youtube.com/watch?v=BBBB
    # comentários começam com # — são ignorados
    https://youtube.com/watch?v=CCCC
"""

import os
import sys
import time
import argparse
from pathlib import Path
from main import rodar


def ler_urls(source: str) -> list:
    """Lê URLs de arquivo ou de stdin."""
    if source == "-":
        linhas = sys.stdin.readlines()
    else:
        linhas = Path(source).read_text(encoding="utf-8").splitlines()

    urls = []
    for l in linhas:
        l = l.strip()
        if not l or l.startswith("#"):
            continue
        urls.append(l)
    return urls


def main():
    parser = argparse.ArgumentParser(description="Processamento em lote do pipeline de cortes")
    parser.add_argument("source", help="Arquivo com URLs (uma por linha) ou '-' pra stdin")
    parser.add_argument("--person", choices=["renato", "julio", "tati"], required=True)
    parser.add_argument("--temas", default="", help="Temas em alta separados por vírgula")
    parser.add_argument("--delay", type=int, default=10,
                        help="Pausa em segundos entre vídeos (default: 10)")
    parser.add_argument("--stop-on-error", action="store_true",
                        help="Para no primeiro erro em vez de continuar")
    args = parser.parse_args()

    urls = ler_urls(args.source)
    temas = [t.strip() for t in args.temas.split(",") if t.strip()]

    print(f"\n{'='*70}")
    print(f"  Processamento em lote — {len(urls)} vídeos")
    print(f"  Persona: {args.person}")
    print(f"  Temas em alta: {temas if temas else '(nenhum)'}")
    print(f"  Delay entre vídeos: {args.delay}s")
    print(f"{'='*70}\n")

    sucessos = 0
    falhas = []

    for i, url in enumerate(urls, 1):
        print(f"\n┌── [{i}/{len(urls)}] {url}")
        try:
            rodar(url, args.person, temas)
            sucessos += 1
            print(f"└── ✓ ok")
        except Exception as e:
            falhas.append((url, str(e)))
            print(f"└── ✗ falhou: {e}")
            if args.stop_on_error:
                break

        if i < len(urls):
            print(f"\n  ... aguardando {args.delay}s antes do próximo...")
            time.sleep(args.delay)

    print(f"\n{'='*70}")
    print(f"  Concluído: {sucessos}/{len(urls)} sucessos")
    if falhas:
        print(f"\n  Falhas:")
        for url, err in falhas:
            print(f"    • {url}")
            print(f"      → {err[:100]}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
