# Pipeline de Cortes — Ecossistema Cariani

Recebe link de YouTube → transcreve via Groq Whisper → analisa transcrição via Claude aplicando o critério Cariani (Renato ou Júlio) → devolve cortes rankeados num dashboard.

Substitui o trabalho do Gustavo de assistir vídeo inteiro pra escolher trechos. Saída: lista priorizada com timestamp, score, pilar, bordão, justificativa, título sugerido e copy.

---

## Estrutura

```
pipeline_cortes_cariani/
├── README.md                  ← este arquivo
├── SETUP.md                   ← passo a passo de instalação
├── .env.example               ← template das chaves de API
├── requirements.txt           ← dependências Python
├── dashboard.html             ← interface (abre no navegador)
│
├── src/
│   ├── main.py                ← pipeline ponta a ponta (1 vídeo)
│   ├── download.py            ← baixa áudio do YouTube (yt-dlp)
│   ├── transcribe.py          ← transcreve via Groq Whisper Large v3 Turbo
│   ├── analyze.py             ← análise via Claude Sonnet 4.6
│   ├── youtube_meta.py        ← metadados do vídeo (YouTube API)
│   ├── temas_em_alta.py       ← rotina 8h de trends (opcional)
│   ├── library_indexer.py     ← indexa TODOS os vídeos dos canais (free)
│   ├── library_search.py      ← busca tema na biblioteca indexada
│   ├── batch_process.py       ← processa lista de URLs em lote
│   └── daily_routine.py       ← rotina 8h automática (orquestrador)
│
├── prompts/
│   ├── system_analyze.md      ← system prompt do Claude
│   ├── persona_renato.md      ← persona, bordões, palavras vermelhas Renato
│   ├── persona_julio.md       ← persona, bordões, palavras vermelhas Júlio
│   └── persona_tati.md        ← persona, frases-âncora, palavras amarelas Tati
│
└── data/
    ├── audio/                 ← áudios baixados (.mp3)
    ├── transcricoes/          ← transcrições (.json)
    ├── temas/                 ← temas em alta por dia
    ├── relatorios/            ← relatórios diários gerados pela rotina 8h (.md)
    ├── library/               ← biblioteca indexada (1 arquivo por canal)
    │   ├── renato_main.json
    │   ├── cariani_tv.json
    │   ├── tati_main.json
    │   └── julio_main.json
    └── cuts/
        ├── index.js           ← arquivo carregado pelo dashboard
        ├── index.json         ← mesmo conteúdo em JSON
        └── <video_id>.json    ← cortes de cada vídeo
```

---

## Uso rápido

```bash
# 1. Setup (uma vez)
pip install -r requirements.txt
cp .env.example .env
# editar .env com suas chaves

# 2. Rodar em um vídeo (escolhe a persona: renato, julio ou tati)
python src/main.py "https://youtube.com/watch?v=XXXX" --person renato
python src/main.py "https://youtube.com/watch?v=YYYY" --person julio
python src/main.py "https://youtube.com/watch?v=ZZZZ" --person tati

# 3. Rodar com temas em alta do dia
python src/temas_em_alta.py
python src/main.py "https://youtube.com/watch?v=XXXX" --person renato --temas "creatina,treino abc"

# 4. Abrir o dashboard
# Opção A: abrir dashboard.html direto no navegador (funciona, mas sem auto-reload)
# Opção B (recomendado): rodar servidor local
python -m http.server 8000
# abrir http://localhost:8000/dashboard.html
```

---

## Trabalhar com a biblioteca antiga (vídeos que já existem)

Indexar TODOS os vídeos dos canais (uma vez, ~30 min, gratuito):

```bash
# Indexa todos os canais de uma vez (Renato, CarianiTV, Tati, Júlio, RCC)
python src/library_indexer.py all

# Ou só um canal específico
python src/library_indexer.py renato_main
python src/library_indexer.py cariani_tv
python src/library_indexer.py tati_main
python src/library_indexer.py julio_main
```

Buscar tema na biblioteca já indexada (instantâneo):

```bash
# Busca textual (grátis, instantâneo)
python src/library_search.py "creatina retencao"

# Filtrar por personagem
python src/library_search.py "lipedema" --person tati

# Top 5 só (default é 20)
python src/library_search.py "treino abc natural" --person julio --top 5

# Busca semântica via Claude (paga API, entende sinônimos)
python src/library_search.py "suplemento que retem liquido" --semantico
```

A saída já te dá o comando pronto pra processar os top 3 no pipeline.

## Processar vários vídeos de uma vez

Crie um arquivo `videos.txt` com uma URL por linha (linhas com `#` são ignoradas):

```
# Vídeos da semana — Renato
https://youtube.com/watch?v=AAAA
https://youtube.com/watch?v=BBBB
https://youtube.com/watch?v=CCCC
```

Rode:

```bash
python src/batch_process.py videos.txt --person renato --delay 30
```

Ou direto via pipe (combina com library_search):

```bash
python src/library_search.py "lipedema" --person tati --top 5 | grep "youtube.com" | python src/batch_process.py - --person tati
```

---

## Rotina 8h automática (orquestrador)

A rotina 8h faz tudo automaticamente todo dia. Em uma chamada:

1. Busca temas em alta no mundo fitness (Claude + web search)
2. Atualiza incremental a biblioteca dos 5 canais (só vídeos novos)
3. Detecta vídeos publicados nas últimas 24h
4. Roda o pipeline neles (configurável)
5. Cruza temas em alta com biblioteca antiga (sugere reaproveitamento)
6. Gera relatório em `data/relatorios/AAAA-MM-DD.md`

```bash
# Testar sem custo (dry-run)
python src/daily_routine.py --dry-run

# Rodar normal
python src/daily_routine.py

# Customizar
python src/daily_routine.py --hours 48 --max-novos 2
```

**Agendar pra rodar todo dia 8h:** veja SETUP.md seção "Rotina 8h automática" — instruções pra cron (Mac/Linux) e Task Scheduler (Windows).

---

## O que cada componente faz

| Componente | Entrada | Saída | Tempo médio |
|---|---|---|---|
| `download.py` | URL YouTube | `data/audio/<id>.mp3` + metadados | 10–30s |
| `transcribe.py` | mp3 | `data/transcricoes/<id>.json` (segments timestampados) | ~1/10 da duração do vídeo (Groq é rápido) |
| `analyze.py` | transcrição + persona | JSON de cortes rankeados | 15–40s |
| `temas_em_alta.py` | — | `data/temas/AAAA-MM-DD.json` | 20–40s |
| `main.py` | URL + person | tudo acima + atualiza `data/cuts/index.js` | ~2–5 min por vídeo de 1h |
| `library_indexer.py` | nome do canal | `data/library/<channel>.json` (~7.000 vídeos) | ~20-40 min por canal grande |
| `library_search.py` | query + opções | lista de vídeos ranqueados (terminal) | instantâneo (textual) / 10-20s (semântico) |
| `batch_process.py` | arquivo de URLs | roda main.py em todos sequencial | depende do volume |
| `daily_routine.py` | — (lê tudo) | relatório do dia em markdown + processa novos | 5-15 min |

---

## Próximos passos sugeridos (fase 2+)

- Plugar Renato + Júlio + Tati em massa: script que recebe pasta de URLs e roda em lote.
- Agendar a rotina 8h via cron: `0 8 * * * cd /caminho && python src/temas_em_alta.py`.
- Integrar com Drive: ler URLs pendentes de uma planilha do Google Sheets.
- Gerar capas: Claude sugere o frame ideal pra capa de cada corte (timestamp do frame).
- Métricas reais: depois do corte publicado, alimentar de volta com views/likes pra melhorar o scoring (fine-tune do prompt).
