#!/bin/zsh
# Rotina diária do Cortes Cariani — roda sozinho via launchd (6h).
# ORDEM CERTA: 1) pesquisa o dia  2) RECONSTRÓI o painel  3) backup no git.
PROJ="/Users/renatocariani/Downloads/cortes_cariani"
cd "$PROJ" || exit 1
source .venv/bin/activate 2>/dev/null
mkdir -p data/relatorios
LOG="data/relatorios/automacao.log"

echo "===== $(date '+%F %T') — iniciando =====" >> "$LOG"

# 1) PESQUISA do dia (temas, biblioteca, vídeos novos). Se falhar, NÃO trava o resto.
python3 src/daily_routine.py >> "$LOG" 2>&1 || echo "  ⚠ daily_routine falhou — segue pro painel" >> "$LOG"

# 2) RECONSTRÓI o painel SEMPRE (é isso que faz a tela atualizar de verdade).
#    O dossiê já tem auto-refresh: se os temas não forem de hoje, ele mesmo pesquisa.
python3 src/dossie_do_dia.py >> "$LOG" 2>&1

# 3) cortes longos dos setores (Balestrin etc.) — opcional, não trava se falhar
# python3 src/cortes_longos.py "<URL_DO_EPISODIO>" --setor balestrin >> "$LOG" 2>&1 || true

# 4) backup automático no GitHub (painel online atualiza junto)
git add -A >> "$LOG" 2>&1
git commit -m "dossie automatico $(date +%F)" >> "$LOG" 2>&1 || true
git push >> "$LOG" 2>&1 || true

echo "----- fim $(date '+%T') -----" >> "$LOG"
