"""Briefing da manhã — um comando que roda toda a inteligência do dia.

Encadeia: tendência real → fila de oportunidade (cortar/gravar) → onda do concorrente.
Cada etapa salva seu relatório em data/relatorios/. É o "abre e age" da operação.

Uso: python3 src/briefing.py
"""
import os
import sys
import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))


def etapa(titulo, fn):
    print("\n" + "=" * 70)
    print(f"  {titulo}")
    print("=" * 70)
    try:
        fn()
    except Exception as e:
        print(f"  (pulei — {str(e)[:80]})")


def rodar():
    print(f"# BRIEFING DA MANHÃ — {datetime.date.today():%d/%m/%Y}")

    def temas():
        import trends; trends.rodar()
    def oport():
        import oportunidade; oportunidade.relatorio()
    def conc():
        import concorrente_onda; concorrente_onda.relatorio()

    etapa("1/3 · Tendências reais do dia", temas)
    etapa("2/3 · Fila de oportunidade (cortar agora / gravar)", oport)
    etapa("3/3 · Onda do concorrente", conc)

    print("\n" + "=" * 70)
    print("  Relatórios salvos em data/relatorios/. Pra minerar tema dentro das lives:")
    print('     python3 src/garimpo.py "<tema>"')
    print("  Pra produzir os cortes (clipe+legenda+ficha pro CutPro):")
    print("     python3 src/produzir.py <video_id> --top 5")
    print("=" * 70)


if __name__ == "__main__":
    rodar()
