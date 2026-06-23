# 🗺️ MAPA DO SISTEMA — Pipeline de Cortes Cariani

> Documento de migração. Descreve estrutura, fluxo, serviços, env e pontos frágeis.
> **Nenhum segredo é exposto** — todos os valores sensíveis aparecem como `<REDACTED>`.
> Python do ambiente atual: **3.10.12**.

---

## 1. Árvore de arquivos (linhas por arquivo)

> Omitidos: `__pycache__`, caches binários, áudios/clipes gerados.

```
pipeline_cortes_cariani/
├── .env                         23   (SEGREDO — não migrar com valores; ver §5)
├── .env.example                 27   (template das variáveis)
├── requirements.txt             12
├── README.md                   187
├── SETUP.md                    169
├── CONTEXTO.md                  27   (notas: "Mauricião" ≠ "maldição", etc.)
├── MAPA_DO_SISTEMA.md           87   (mapa anterior, p/ CutPro)
├── GUIA_INTELIGENCIA.md        108
├── ENTREGA_DIA_1.md             70
├── ROTEIRO_DE_VALIDACAO.md      55
├── RELATORIO_TESTE_COMPLETO.md  46
├── SO_Cortes_..._auditado.docx 136
│
├── app/                              (frontend novo — painel/Netlify)
│   ├── index.html              283   lê window.PAINEL e renderiza o painel
│   ├── painel.js                 1   window.PAINEL = {...}  (gerado pelo dossiê)
│   └── logo.svg                 14   marca RK (fallback p/ logo.png)
├── dashboard.html              459   (dashboard antigo do editor; lê CUTS_INDEX)
│
├── prompts/
│   ├── system_analyze.md       104   system prompt do analisador de cortes
│   ├── persona_renato.md        39
│   ├── persona_julio.md         42
│   └── persona_tati.md          83
│
├── src/                              (todo o código — detalhado no §2)
│   └── *.py  (43 módulos)
│
└── data/                             (estado/saída; ver §6)
    ├── temas/        (tendências do dia: ultimo.json, AAAA-MM-DD.json)
    ├── library/      (índice do acervo: renato_main.json 57k linhas, etc.)
    ├── transcricoes/ (JSON por vídeo: text_full+segments)
    ├── cuts/         (cortes por vídeo + index.json/index.js)
    ├── feedback/     (calibragem, decisões, snapshots de performance)
    ├── voices/       (voiceprints .npy: renato, julio)
    └── relatorios/   (saídas .md diárias: dossiê, aposta, calendário…)
```

Maiores fontes de dados: `data/library/renato_main.json` (~57k linhas, índice do acervo) e as transcrições (`Pv3wkrXWDV4.json` ~2k, `5XPB3FFndTM.json` ~1.5k).

---

## 2. O que cada módulo faz (e o que importa)

### Núcleo do pipeline (1 vídeo → cortes)
| Arquivo | Linhas | O que faz | Importa/chama |
|---|---|---|---|
| `main.py` | 173 | Orquestra 1 vídeo: metadados→áudio→transcrição→análise→verificação→voz→salva cuts + atualiza index. | download, transcribe, analyze, youtube_meta, verify, speaker_id |
| `download.py` | 55 | Baixa o áudio do YouTube. | **yt-dlp** (subprocess) |
| `transcribe.py` | 115 | Transcreve áudio (Whisper); faz chunking p/ arquivos >25MB. | **groq**, ffmpeg (subprocess) |
| `analyze.py` | 94 | Manda transcrição+persona+temas ao Claude e recebe cortes (JSON). | **anthropic**, prompts/ |
| `verify.py` | 142 | Verificador de fidelidade: localiza abertura/fecho nos segments, refaz fronteira real, rejeita <8s, funde sobrepostos. | só `re`, `difflib` (sem rede) |
| `youtube_meta.py` | 53 | Metadados do vídeo (título, descrição, duração). | **googleapiclient** (YouTube Data API) |
| `speaker_id.py` | 85 | Identifica quem fala por voz (voiceprint). Opcional; ignora se libs ausentes. | resemblyzer+torch, ffmpeg |
| `repersona.py` | 92 | Reescreve o tom de cortes de convidado na persona certa. | anthropic (lazy) |

### Inteligência / pesquisa (o que cortar)
| Arquivo | Linhas | O que faz | Importa/chama |
|---|---|---|---|
| `trends.py` | 195 | Coleta tendência real (Google Trends) + YouTube + curadoria Claude. Fonte principal de "em alta". | **pytrends**, googleapiclient, anthropic |
| `temas_em_alta.py` | 19 | Atalho fino que reexporta `trends.py`. | trends |
| `tendencia_memoria.py` | 67 | Lê histórico de temas e separa consolidando / novo / esfriando (sazonalidade). | só stdlib |
| `oportunidade.py` | 162 | Cruza tema quente × acervo → fila priorizada "cortar vs gravar" + gap. | busca_local |
| `concorrente_onda.py` | 93 | Pega virais de canais concorrentes BR e sugere vídeo do Renato p/ surfar a onda. | googleapiclient, busca_local |
| `garimpo.py` | 97 | Tema quente → trecho exato dentro de uma live. | busca_transcricao, busca_local |
| `lives.py` | 62 | Lista as lives/vídeos longos (onde está o conteúdo multi-tema). | stdlib |
| `triagem_lives.py` | 124 | Separa live de CONTEÚDO (tem corte) de ENTRETENIMENTO. | anthropic (lazy) |
| `cortes_existentes.py` | 70 | Usa canais de cortes (CarianiTV/RCC) como sinal + dedup de estilo. | sklearn (TF-IDF) |
| `dedup.py` | 87 | Evita transcrever/cortar o mesmo conteúdo 2x. | stdlib |

### Busca no acervo
| Arquivo | Linhas | O que faz | Importa/chama |
|---|---|---|---|
| `busca_local.py` | 76 | Busca por título no acervo via TF-IDF (offline, grátis). É a base de várias outras. | **scikit-learn** |
| `busca_semantica.py` | 89 | Busca por significado (embeddings), com cache. Opcional. | sentence-transformers, busca_local |
| `busca_transcricao.py` | 110 | Busca DENTRO das transcrições em janelas de ~75s. | numpy, busca_local |
| `library_indexer.py` | 232 | Indexa todos os vídeos públicos de um canal (incremental, dedup). | **googleapiclient** |
| `library_search.py` | 210 | Busca textual + semântica na biblioteca indexada. | anthropic (lazy) |

### Produção (corte → entregável)
| Arquivo | Linhas | O que faz | Importa/chama |
|---|---|---|---|
| `precorte.py` | 43 | Baixa só o trecho [start,end] e gera o MP4. | yt-dlp (subprocess) |
| `legendas.py` | 56 | Gera .srt re-baseado em 00:00 a partir dos segments. | stdlib |
| `produzir.py` | 83 | Pacote por corte: MP4 + SRT + ficha (capa/copy). | precorte, legendas |
| `reframe.py` | 74 | Auto-reframe 16:9→9:16 seguindo o rosto. | **opencv (cv2)**, ffmpeg |
| `capa.py` | 93 | Escolhe melhor frame de capa (visão do Claude). | anthropic, ffmpeg |
| `momentos_visuais.py` | 103 | Flag de momentos visualmente fortes (reação, demo). | anthropic, ffmpeg |
| `multiformato.py` | 92 | 1 corte → N peças (Reels/TikTok/Short/carrossel/thread/news). | anthropic (lazy) |

### Performance / aprendizado (o volante)
| Arquivo | Linhas | O que faz | Importa/chama |
|---|---|---|---|
| `publicacoes.py` | 104 | Liga corte→post publicado e puxa métricas reais. | googleapiclient |
| `performance.py` | 124 | Deriva pesos por característica do que performou. | stdlib |
| `calibrar.py` | 130 | Calibra score a partir das views dos canais de corte. | anthropic (lazy) |
| `monitor.py` | 112 | Volante semanal: vigia canais de corte e re-calibra sozinho. | calibrar |
| `feedback_report.py` | 151 | Lê decisões do editor (cortado/descartado) e recomenda ajustes. | stdlib |

### Orquestração / saída / entrega
| Arquivo | Linhas | O que faz | Importa/chama |
|---|---|---|---|
| `daily_routine.py` | 309 | **Rotina das 8h**: temas→biblioteca incremental→detecta vídeos novos→processa→cruza→relatório. | library_indexer, library_search, temas_em_alta, oportunidade |
| `dossie_do_dia.py` | 148 | **Roda tudo junto** e gera `app/painel.js` + dossiê .md (fonte do painel). | concorrente_onda, tendencia_memoria, oportunidade |
| `aposta_do_dia.py` | 91 | Digest curto "certeiro" pra colar no grupo. | stdlib + dados |
| `briefing.py` | 51 | Encadeia tendência→oportunidade→onda do concorrente num comando. | (chama módulos de inteligência) |
| `calendario.py` | 84 | Propõe a grade da semana a partir da fila de oportunidade. | oportunidade |
| `perguntar.py` | 50 | "Cérebro do Renato": pergunta ao acervo, responde com base no que ele falou. | busca_transcricao, anthropic |
| `batch_process.py` | 95 | Roda o pipeline (`main.rodar`) em uma lista de URLs. | main |
| `transcrever_lote.py` | 92 | Transcreve lives em lote, com dry-run e teto de gasto. | (transcribe via fluxo) |
| `server.py` | 81 | Servidor local do dashboard + coleta de feedback (HTTP). | http.server (stdlib) |

---

## 3. Fluxo ponta a ponta

**A) Rotina diária automática (disparo: cron/agendador 8h → `daily_routine.py`)**
1. `temas_em_alta.rodar()` → **`trends.py`** coleta o que está em alta (Google Trends + YouTube + curadoria Claude) → salva `data/temas/ultimo.json`.
2. `atualizar_biblioteca_incremental()` → **`library_indexer.indexar_canal`** atualiza o índice do acervo (só vídeos novos).
3. `detectar_videos_novos()` → acha uploads das últimas 24h.
4. `cruzar_temas_biblioteca()` + **`oportunidade.analisar()`** → fila priorizada (cortar vs gravar).
5. `processar_videos_novos()` → chama o pipeline de corte (B) nos candidatos.
6. `gerar_relatorio()` → relatórios .md em `data/relatorios/`.
7. **`dossie_do_dia.rodar()`** consolida tudo (tendência+concorrência+sazonalidade+performance+acervo) e escreve **`app/painel.js`** → o painel (`app/index.html`) lê isso.

**B) Pipeline de 1 vídeo (`main.py rodar(url)`)**
1. `[1/4]` **`youtube_meta.metadados(url)`** — título/descrição/duração (YouTube API).
2. `[2/4]` **`download.baixar_audio`** — yt-dlp baixa o áudio.
3. `[3/4]` **`transcribe.transcrever`** — Groq Whisper → `segments` (com chunking se >25MB); cacheia em `data/transcricoes/<id>.json`.
4. `[4/4]` **`analyze.analisar`** — Claude lê transcrição+persona+temas → cortes candidatos (JSON).
5. **`verify.verificar_e_corrigir`** — refaz a fronteira real, rejeita curtos/inventados, funde sobrepostos.
6. (opcional) **`speaker_id`** — confere por voz quem fala.
7. Salva `data/cuts/<id>.json` e `atualizar_index()` → `data/cuts/index.json` + `index.js` (window.CUTS_INDEX).

**C) Produção do entregável (`produzir.py`)**
Corte aprovado → **`precorte`** (MP4 do trecho) + **`legendas`** (.srt) + ficha; opcional **`reframe`** (9:16), **`capa`**, **`multiformato`**.

**D) Aprendizado (semanal — `monitor.py` / `calibrar.py` / `performance.py`)**
Vigia canais de corte públicos → views reais → recalcula pesos do score (`data/feedback/calibragem_titulo.json`) → o ranking do próximo dia já sai calibrado.

---

## 4. Serviços externos e APIs

| Serviço | Para quê | Chamado em |
|---|---|---|
| **Anthropic Claude** (`anthropic`) | análise de cortes, curadoria de temas, capa/visão, multiformato, calibração, perguntas | analyze, trends, capa, momentos_visuais, multiformato, calibrar, repersona, perguntar, triagem_lives, library_search |
| **Groq Whisper** (`groq`) | transcrição de áudio | transcribe.py |
| **YouTube Data API v3** (`googleapiclient`) | metadados, indexar canais, concorrentes, métricas de publicação | youtube_meta, library_indexer, concorrente_onda, publicacoes, trends |
| **Google Trends** (`pytrends`) | termos em alta no Brasil (fonte principal "em alta") | trends.py |
| **yt-dlp** (binário/lib) | baixar áudio e trechos | download.py, precorte.py |
| **ffmpeg / ffprobe** (binário) | chunking de áudio, extração de frames, reframe | transcribe, capa, momentos_visuais, reframe, speaker_id |

---

## 5. Variáveis de ambiente (`.env`) — nomes e descrição, **sem valores**

| Nome | Descrição | Valor |
|---|---|---|
| `ANTHROPIC_API_KEY` | chave da API Claude (análise) | `<REDACTED>` |
| `GROQ_API_KEY` | chave da API Groq (transcrição Whisper) | `<REDACTED>` |
| `YOUTUBE_API_KEY` | chave YouTube Data API v3 (metadados/índice) | `<REDACTED>` |
| `CLAUDE_MODEL` | modelo Claude a usar (ex.: produção vs rápido) | `<REDACTED>` |
| `GROQ_WHISPER_MODEL` | modelo Whisper no Groq | `<REDACTED>` |
| `DATA_DIR` | raiz dos dados/saídas (default `./data`) | `<REDACTED>` |
| `LANG` | idioma da transcrição/análise (`pt`) | `<REDACTED>` |

> ⚠️ **Segurança da migração:** não leve o `.env` com valores. Recrie as 3 chaves no novo ambiente. As chaves atuais já apareceram em texto neste workspace — **recomendo revogá-las e gerar novas** antes/depois de migrar.

---

## 6. Dados — o que é `5XPB3FFndTM.json`

`5XPB3FFndTM` é um **ID de vídeo do YouTube**. Existem dois arquivos com esse nome, em pastas diferentes (origem = saída do pipeline para esse vídeo):

**a) `data/transcricoes/5XPB3FFndTM.json`** (~1.481 linhas) — **saída da transcrição** (Groq Whisper).
Schema de alto nível:
```
{ "text_full": "<transcrição inteira>",
  "segments": [ { "start": float, "end": float, "text": str }, ... 295 itens ],
  "language": "pt",
  "duration": float_segundos }
```

**b) `data/cuts/5XPB3FFndTM.json`** (~85 linhas) — **saída da análise** (cortes desse vídeo).
Schema de alto nível:
```
{ "video_id", "person", "analyzed_at", "total_candidates_evaluated",
  "processed_at", "video_meta": {título, duração...},
  "cuts": [ { "id", "start_seconds", "end_seconds", "duration_seconds",
              "start_timestamp", "end_timestamp", "score",
              "pilar_primario", "pilares_detectados", "bordao_presente",
              "tema_alta_match", "flag", "palavras_amarelas_detectadas",
              "title_sugerido", "copy_short_sugerida", "transcricao_trecho",
              "evidencia_literal", "justificativa_score" }, ... 3 cortes ] }
```
> Observação: este arquivo (`cuts/5XPB3FFndTM`) está num formato **mais antigo** — não tem `headline_post`, `tipo_corte`, `publicavel_sozinho`, `falante_voz` que os cortes novos (ex.: `FCqbbgEEC7w.json`) já trazem. Ver §8.

Outros dados relevantes: `data/library/*_main.json` (índice do acervo por canal), `data/temas/ultimo.json` (em alta do dia), `data/feedback/calibragem_titulo.json` (pesos aprendidos), `data/voices/*.npy` (voiceprints).

---

## 7. Dependências

**Python:** 3.10.12 (ambiente atual).

**pip (`requirements.txt`):**
```
anthropic>=0.40.0
groq>=0.15.0
yt-dlp>=2025.5.0
google-api-python-client>=2.130.0
python-dotenv>=1.0.0
requests>=2.32.0
pytrends>=4.9.0
```
**Opcionais (não no requirements, instalar só se usar):**
- `scikit-learn` — usado por `busca_local.py` e `cortes_existentes.py` (TF-IDF). ⚠️ é import direto, então hoje é **obrigatório de fato** p/ a inteligência (ver §8).
- `numpy` — busca_transcricao, speaker_id.
- `sentence-transformers` — busca semântica (opcional).
- `resemblyzer` + `torch` — identificação por voz (opcional, pesado).
- `opencv-python` (cv2) — `reframe.py` (opcional).

**Binários externos do SO:**
- **ffmpeg** + **ffprobe** (obrigatório p/ transcrição com chunking, capa, reframe).
- **yt-dlp** (vem via pip, mas precisa de ffmpeg p/ pós-processar).

---

## 8. Pontos frágeis / TODOs

1. **`scikit-learn` e `numpy` não estão no `requirements.txt`**, mas `busca_local.py` (base de oportunidade/concorrência) os importa direto no topo. No novo ambiente, **adicionar ao requirements** ou a inteligência quebra. (Os demais — anthropic/cv2/sentence-transformers — são import lazy e degradam com elegância.)
2. **Formato de cortes inconsistente:** `cuts/5XPB3FFndTM.json` é do schema antigo (sem `headline_post`/`tipo_corte`/`publicavel_sozinho`/`falante_voz`). O painel novo (`dossie_do_dia._cuts_prontos`) usa `.get(...)` com default, então não quebra, mas esse vídeo aparece "pobre". Reprocessar p/ uniformizar.
3. **IDs de canal hardcoded:** os canais concorrentes (Toguro/Muzy/Twin/Bottura) e os do Renato estão fixos em `concorrente_onda.py` / `library_indexer.py`. Handles de **Tati e Júlio não resolvem** (precisam das URLs reais).
4. **Acervo ainda não totalmente indexado/transcrito:** o índice completo (~7.748 vídeos) e a transcrição das lives precisam rodar no Mac (rede/tempo). Hoje o painel roda com amostra parcial.
5. **Google Trends (pytrends) sofre rate-limit (HTTP 429).** `trends.py` tem fallback, mas em rajada pode vir vazio — rodar com parcimônia/retry.
6. **Dois frontends coexistem:** `dashboard.html` (antigo, lê `CUTS_INDEX`) e `app/index.html` (novo, lê `PAINEL`). Na migração, decidir qual é o oficial (o novo `app/`).
7. **`logo.png` ausente:** o header usa `app/logo.svg` como fallback; salvar a logo oficial em `app/logo.png` no novo ambiente.
8. **Janela de execução do sandbox:** modelos lentos (Sonnet) estouram timeouts curtos; no ambiente novo, rodar as etapas pesadas (transcrição/análise/índice) sem limite agressivo de tempo.
9. **Segredos:** `.env` contém chaves reais — migrar **sem** os valores e **rotacionar** (ver §5).
