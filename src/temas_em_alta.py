"""Temas em alta do dia — agora com DADO REAL (Google Trends + curadoria).

Este arquivo virou um atalho fino para src/trends.py, que coleta tendência real
(Google Trends Brasil) e estrutura em temas do nicho. Mantém o mesmo nome/uso de antes,
então o daily_routine.py e o main.py continuam funcionando.

Uso:
    python src/temas_em_alta.py     # gera data/temas/AAAA-MM-DD.json
"""
from trends import rodar, google_trends, curar  # noqa: F401  (reexporta)


def buscar_temas():
    """Compatibilidade: devolve o dict de temas do dia (via fonte real)."""
    return rodar()


if __name__ == "__main__":
    rodar()
