# SETUP — Passo a passo

Roteiro pra você (ou alguém do time) deixar o pipeline rodando do zero. Tempo total: ~30 min de setup.

---

## 1. Criar as 3 chaves de API

### 1.1 Anthropic (Claude) — análise
1. Entrar em https://console.anthropic.com/settings/keys
2. Login (criar conta se ainda não tem)
3. Adicionar US$ 50 de crédito em Billing → Add Credit
4. Settings → API Keys → Create Key → copiar
5. Cola no `.env` em `ANTHROPIC_API_KEY=`

### 1.2 Groq — transcrição
1. Entrar em https://console.groq.com/keys
2. Login com Google
3. Create API Key → copiar
4. Tier grátis já dá pra começar (uns 10–20 vídeos/dia gratuitos). Quando crescer, adicionar pagamento.
5. Cola no `.env` em `GROQ_API_KEY=`

### 1.3 YouTube Data API — metadados
1. Entrar em https://console.cloud.google.com
2. Criar novo projeto (ex: "Pipeline Cariani")
3. APIs & Services → Library → buscar "YouTube Data API v3" → Enable
4. APIs & Services → Credentials → Create Credentials → API Key → copiar
5. Cola no `.env` em `YOUTUBE_API_KEY=`

---

## 2. Instalar dependências

```bash
cd pipeline_cortes_cariani

# Python 3.10+ recomendado
pip install -r requirements.txt

# yt-dlp precisa de ffmpeg pra converter pra mp3
# Mac:
brew install ffmpeg
# Linux:
sudo apt install ffmpeg
# Windows:
# baixa em https://www.gyan.dev/ffmpeg/builds/ e adiciona no PATH
```

---

## 3. Configurar .env

```bash
cp .env.example .env
# abre .env e cola as 3 chaves
```

---

## 4. Testar com um vídeo

```bash
# pega um vídeo recente do canal do Renato
python src/main.py "https://www.youtube.com/watch?v=ID_DO_VIDEO" --person renato

# saída esperada:
# [1/4] Pegando metadados...
# [2/4] Baixando áudio...
# [3/4] Transcrevendo via Groq Whisper...
# [4/4] Analisando trechos via Claude...
# ✓ Pronto. N cortes salvos em data/cuts/<id>.json
```

---

## 5. Abrir o dashboard

**Opção A — direto no navegador (mais simples)**
```bash
# clica em dashboard.html duas vezes no Finder/Explorer
```
Funciona, mas o botão "atualizar" não consegue carregar JSON via file://. Pra recarregar, dá F5 — ele lê o `data/cuts/index.js`.

**Opção B — servidor local (recomendado)**
```bash
cd pipeline_cortes_cariani
python -m http.server 8000
# abrir http://localhost:8000/dashboard.html
```
Botão "atualizar" agora funciona sem F5.

---

## 6. Rotina 8h automática (recomendado)

A rotina 8h faz TUDO automaticamente todo dia: busca temas em alta, atualiza biblioteca, detecta vídeos novos, roda pipeline neles, cruza temas com biblioteca antiga e gera relatório do dia em markdown.

### Testar primeiro (dry-run, zero custo)

```bash
cd pipeline_cortes_cariani
python src/daily_routine.py --dry-run
```

Isso gera um relatório fake em `data/relatorios/AAAA-MM-DD.md` que você pode abrir pra ver o formato. Não roda o pipeline (não gasta API).

### Rodar de verdade (manual)

```bash
python src/daily_routine.py
# ou com janela maior pra pegar vídeos das últimas 48h:
python src/daily_routine.py --hours 48 --max-novos 2
```

### Agendar pra rodar todo dia 8h

**Mac/Linux — crontab**
```bash
crontab -e
# adicionar (ajustar o caminho):
0 8 * * * cd /Users/SEU_USUARIO/pipeline_cortes_cariani && /usr/bin/python3 src/daily_routine.py >> data/cron.log 2>&1
```

**Windows — Task Scheduler**
1. Abrir Task Scheduler → Create Basic Task
2. Trigger: Daily, 8:00
3. Action: Start a program
4. Program: `python`
5. Arguments: `C:\caminho\pipeline_cortes_cariani\src\daily_routine.py`
6. Start in: `C:\caminho\pipeline_cortes_cariani`

### O que o relatório do dia contém

Arquivo `data/relatorios/AAAA-MM-DD.md`:
- **Temas em alta** do dia (com nível e motivo)
- **Polêmicas e viralizadas** do nicho fitness
- **Biblioteca atualizada** (quantos vídeos novos por canal)
- **Vídeos novos detectados** (últimas 24h)
- **Processados pelo pipeline** (já viraram cortes)
- **Sugestões da biblioteca antiga** — vídeos antigos que casam com tema em alta hoje, COM comando pronto pra processar

### Custo estimado da rotina diária

- temas_em_alta (Claude com web search): ~R$ 0,30/dia
- biblioteca incremental (YouTube API): R$ 0
- pipeline em ~3 vídeos novos: ~R$ 3-5/dia
- **Total: ~R$ 100-150/mês rodando todo dia**

---

## 7. Manutenção

- Cada vídeo deixa um mp3 e um JSON de transcrição em `data/`. Limpar a cada 30 dias.
- `data/cuts/index.js` cresce com o tempo. Quando passar de 200 cortes, recomendo arquivar os mais antigos.
- Custos de API: monitora em https://console.anthropic.com/usage e https://console.groq.com/usage.

---

## Troubleshooting

**"ANTHROPIC_API_KEY not set"** → o `.env` não está sendo lido. Confirma que está na raiz do projeto.

**"yt-dlp: ERROR: Unable to download webpage"** → vídeo privado, ou yt-dlp desatualizado. Roda `pip install --upgrade yt-dlp`.

**"groq.BadRequestError: file size too large"** → vídeo maior que 25MB de áudio. Groq limita. Solução: cortar em chunks no `transcribe.py` (não implementado no MVP — me avisa quando precisar e eu adiciono).

**"JSON decode error" no analyze.py** → Claude devolveu prosa em vez de JSON. Acontece em vídeos muito curtos ou com transcrição confusa. Roda de novo; se repetir, me manda o vídeo e eu ajusto o prompt.

**Dashboard não mostra cortes** → abra o console do navegador (F12) e veja erro. Provável: `data/cuts/index.js` não existe. Roda o pipeline em pelo menos 1 vídeo primeiro.
