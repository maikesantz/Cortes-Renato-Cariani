# Camada de Inteligência — guia de uso

O que decide **qual vídeo do acervo virar corte hoje**, conectando o que o público está buscando com o que o Renato já gravou. Tudo local e praticamente **de graça** (Google Trends + YouTube API são grátis; só a curadoria do Claude custa centavos/dia).

## Fluxo do dia

```
# UMA VEZ (setup):
python3 src/library_indexer.py renato_main      # indexa o acervo (ou 'all', ou --incremental)

# TODA MANHÃ (um comando só):
python3 src/briefing.py                         # tendência + fila de oportunidade + onda do concorrente

# PLANEJAR A SEMANA:
python3 src/calendario.py                       # grade dos 7 dias (o que cortar/gravar, por horário)

# AGIR:
python3 src/garimpo.py "<tema quente>"          # acha o tema dentro das lives (timestamp exato)
python3 src/main.py "URL" --person renato       # gera os cortes de um vídeo
python3 src/produzir.py <video_id> --top 5      # empacota clipe + legenda + ficha pro CutPro
```

## Produção — saída pronta pro editor / CutPro

| Script | Função |
|---|---|
| `precorte.py` | Baixa só o trecho e gera o **MP4 cortado** (yt-dlp por seção — funciona até em live de horas). |
| `legendas.py` | Gera o **.srt** do corte a partir da transcrição (legenda grátis pro CutPro). |
| `produzir.py` | Empacota cada corte: **MP4 + SRT + ficha** (capa/título/copy/pilar/falante). |
| `repersona.py` | Reescreve título/capa/copy de corte de **convidado** no tom do falante real (voz). |
| `cortes_existentes.py` | Mostra se o time **já cortou** aquele tema (dedup + referência de estilo). |
| `multiformato.py` | De 1 corte gera **Reels + TikTok + Short + carrossel + thread + newsletter** (no tom do personagem). |
| `capa.py` | Visão do Claude escolhe o **melhor frame de capa** (rosto/expressão de pico). |
| `reframe.py` | Converte o clipe 16:9 em **9:16 vertical seguindo o rosto** (OpenCV), com áudio. |
| `momentos_visuais.py` | Flaga **momentos visuais fortes** (reação/expressão) pra cortar pelo que é mostrado. |
| `perguntar.py` | Cérebro do Renato: pergunta sobre o que ele já disse → resposta **com citação e timestamp**. |
| `transcrever_lote.py` | Transcreve as lives de conteúdo em **lote, com teto de gasto** (dry-run por padrão). |

## O que cada peça faz

| Script | Função | Custo |
|---|---|---|
| `library_indexer.py` | Mapeia os vídeos dos canais (título, views, data). `--limit=N` indexa só os N recentes. | Grátis (cota API) |
| `trends.py` | Tendência **real**: Google Trends (busca) + comentários do público (demanda) + vídeos do nicho bombando (concorrência) → Claude limpa em temas. | ~R$0,10/dia |
| `busca_local.py` | Busca no acervo por relevância (TF-IDF), local e offline. | Grátis |
| `oportunidade.py` | Cruza tema quente × material no acervo × tempo sem postar → **fila CORTAR** + **buracos GRAVAR**. | Grátis |
| `tendencia_memoria.py` | Acumula os dias e separa tendência que **consolida** vs **modinha**. | Grátis |
| `concorrente_onda.py` | Vídeo bombando de concorrente BR (Toguro, Muzy, Twin…) → vídeos do Renato sobre o mesmo tema pra **surfar a onda**. | Grátis (cota API) |
| `busca_semantica.py` | Busca no acervo por **significado** (embeddings locais — pega sinônimo). Substitui a busca semântica paga do Claude por uma grátis/offline. | Grátis (após `pip install sentence-transformers`) |

## Score de oportunidade

`oportunidade.py` entrega duas listas:

- **🔪 CORTAR AGORA** — tema em alta onde o Renato já tem material parado. Ranqueado por: o quanto sobe × quantos vídeos existem × há quanto tempo não posta. Já vem com o comando pronto.
- **🎥 GRAVAR** — tema em alta **sem** material no acervo. Não é corte: é **pauta de gravação**.

## Minerar as LIVES (onde está o conteúdo multi-tema)

As lives de horas têm dezenas de temas, mas o título não diz nenhum — busca por metadado não acha. A solução é buscar na **transcrição**.

| Script | Função |
|---|---|
| `lives.py` | Lista as lives do acervo (ranqueadas por views) com custo de transcrição. |
| `busca_transcricao.py` | Busca um tema **dentro** das transcrições → vídeo + **timestamp exato**. |
| `garimpo.py` | Junta tudo: tema → trechos já achados + lives candidatas → transcreve sob demanda → re-busca. |

Fluxo: `python3 src/garimpo.py "creatina"` mostra o que já dá pra cortar e quais lives minerar; `--transcrever 2` transcreve as 2 melhores e acha o tema lá dentro. Transcrição é **sob demanda** (você minera quando o tema esquenta), e o que transcreve fica buscável pra sempre.

## Loop de performance (o sistema aprende com a realidade)

Fecha o ciclo: o que foi publicado e performou re-prioriza o que cortar a seguir.

| Script | Função |
|---|---|
| `publicacoes.py` | Registra o corte publicado (corte→post) e puxa **views/likes/comments** reais (YouTube). |
| `performance.py` | Aprende o que rende por característica (pilar/tipo/duração/falante/bordão) → gera pesos que entram no scoring. Cada corte passa a ter um **fator de performance** e uma **prioridade** (score × fator). |

Fluxo: publicou → `publicacoes.py registrar ...` → `publicacoes.py atualizar` (puxa métricas) → `performance.py` (aprende). A partir de ~8 cortes publicados, o sistema prioriza sozinho o perfil que o algoritmo já provou que funciona.

**Upgrade futuro:** retenção e Instagram precisam de acesso extra (YouTube Analytics OAuth / IG Graph API). Por ora o loop usa views/likes/comments do YouTube (que a chave atual já puxa) — já é um sinal forte.

## Sempre em alta performance (o volante)

| Script | Quando | Função |
|---|---|---|
| `calibrar.py` | sob demanda | Deriva os pesos do score do que o público **já premiou** (título grátis; `--conteudo N` transcreve amostra). |
| `monitor.py` | semanal (cron) | Vigia os cortes publicados, re-calibra e detecta **o que acelerou/esfriou** (drift). Digest semanal. |
| `aposta_do_dia.py` | diário (cron + agendado) | O **"certeiro do dia"** pra colar no grupo: provado + em alta + aposta nº1. |

Cron sugerido (no Mac):
```
0 8 * * *  cd ~/Documents/pipeline_cortes_cariani && python3 src/aposta_do_dia.py
0 9 * * 1  cd ~/Documents/pipeline_cortes_cariani && python3 src/monitor.py
```
(O `aposta_do_dia` também já está como **tarefa agendada** no app, rodando toda manhã.)

## Instagram / TikTok (honesto)

Não têm feed público grátis de tendência. O que o time observar nessas plataformas vai em `data/temas/manual.json` e entra na mistura. Sem fingir que existe API.

## Pendência pra você resolver (achado de auditoria)

Os handles `@taticariani_` e `@juliobalestrinoficial` **não resolveram** para canais do YouTube (provavelmente são Instagram, ou o canal tem outro handle). O indexador agora **falha em vez de indexar o canal errado** (antes pegava o do Renato em silêncio). Pra indexar Tati/Júlio, me passe a **URL real do canal YouTube** de cada um que eu corrijo no `CHANNELS`.

## Limitação conhecida

O match hoje é por **título/descrição**. O salto de qualidade é casar por **transcrição** (o que é dito), que melhora sozinho conforme os vídeos passam pelo pipeline. Upgrade futuro: trocar o TF-IDF por embeddings neurais pra pegar sinônimo de verdade.
