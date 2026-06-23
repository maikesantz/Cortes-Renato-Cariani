# 🚀 Migração — Quickstart

Passo a passo pra subir o projeto num ambiente novo. Detalhe completo de cada arquivo está em **`MAPA_MIGRACAO.md`**.

## 1. Pré-requisitos do sistema
- **Python 3.10+** (testado em 3.10.12).
- **ffmpeg + ffprobe** (obrigatório):
  - macOS: `brew install ffmpeg`
  - Ubuntu/Debian: `sudo apt-get install ffmpeg`

## 2. Dependências Python
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```
> Opcionais (só se for usar os módulos): `sentence-transformers` (busca semântica), `resemblyzer torch` (voz), `opencv-python` (reframe). Veja os comentários no `requirements.txt`.

## 3. Segredos (.env) — NÃO migrar com valores
1. Copie o template: `cp .env.example .env`
2. **Gere chaves NOVAS** (não reaproveite as antigas — elas já circularam):
   - `ANTHROPIC_API_KEY` → https://console.anthropic.com/settings/keys
   - `GROQ_API_KEY` → https://console.groq.com/keys
   - `YOUTUBE_API_KEY` → https://console.cloud.google.com (ative "YouTube Data API v3")
3. Cole cada valor no `.env`. Os demais campos (`CLAUDE_MODEL`, `GROQ_WHISPER_MODEL`, `DATA_DIR`, `LANG`) já vêm com default bom.

> ⚠️ Revogue as chaves antigas no painel de cada provedor após confirmar que as novas funcionam.

## 4. Teste de fumaça (sem gastar quase nada)
```bash
# inteligência do dia (gera app/painel.js + dossiê .md)
python3 src/dossie_do_dia.py

# pipeline em 1 vídeo (baixa, transcreve, analisa, verifica)
python3 src/main.py "https://www.youtube.com/watch?v=<ID>"
```
Abra `app/index.html` no navegador — o painel lê `app/painel.js`.

## 5. Rotina automática (opcional)
`src/daily_routine.py` é o orquestrador das 8h (temas → biblioteca → vídeos novos → cortes → dossiê). Agende via cron/agendador do novo ambiente.

## 6. O que rodar no ambiente final (pesado, fora do sandbox)
- **Índice completo do acervo** (~7.748 vídeos): `python3 src/library_indexer.py` (sem `--limit`).
- **Transcrição das lives em lote**: `python3 src/transcrever_lote.py` (começa em dry-run; use `--teto` p/ limitar gasto).

## 7. Logo do app
Salve a logo oficial como **`app/logo.png`** (o header usa `app/logo.svg` como fallback enquanto não existir).

## 8. Frontend oficial
Use **`app/`** (novo, lê `window.PAINEL`). O `dashboard.html` na raiz é a versão antiga — pode arquivar.
