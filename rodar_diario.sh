#!/bin/zsh
PROJ="/Users/renatocariani/Downloads/cortes_cariani"
cd "$PROJ" || exit 1
source .venv/bin/activate 2>/dev/null
mkdir -p data/relatorios
LOG="data/relatorios/automacao.log"
echo "===== $(date '+%F %T') — iniciando =====" >> "$LOG"
python3 src/daily_routine.py >> "$LOG" 2>&1 || python3 src/dossie_do_dia.py >> "$LOG" 2>&1
git add -A >> "$LOG" 2>&1
git commit -m "dossie automatico $(date +%F)" >> "$LOG" 2>&1 || true
git push >> "$LOG" 2>&1 || true
echo "----- fim $(date '+%T') -----" >> "$LOG"
