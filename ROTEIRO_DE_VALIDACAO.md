# Roteiro de validação — colocar o sistema na rua

Do mais rápido/barato ao mais real. O objetivo não é "ver funcionar" — é **medir** o que prova (ou derruba) a operação.

---

## Etapa 0 — Pré-requisitos (no Mac)

- [ ] Rodar o índice completo: `python3 src/library_indexer.py renato_main` e `cariani_tv`
- [ ] Conferir que o `.env` está em **Sonnet** (`CLAUDE_MODEL=claude-sonnet-4-6`) — já está
- [ ] (Segurança) trocar as 3 chaves de API por novas
- [ ] Instalar as libs opcionais se for usar voz/visão: `pip install resemblyzer torch sentence-transformers opencv-python-headless`

## Etapa 1 — Primeiro corte real com Sonnet (~R$3, sozinho)

- [ ] Escolher um vídeo de **FALA** do Renato (podcast/explicação, NÃO treino bruto) que o Gustavo conheça
- [ ] `python3 src/main.py "URL" --person renato`
- [ ] Abrir o dashboard e conferir, corte a corte:
  - Os timestamps apontam pro momento certo?
  - A fala citada é literal (fidelidade 100%)?
  - Título/capa fazem sentido?
- [ ] **Me manda o JSON gerado** → calibramos o score juntos (subir/baixar o corte de 6.0)

## Etapa 2 — Teste cego com o Gustavo (O MAIS IMPORTANTE)

- [ ] Pegar um vídeo que ele **já cortou** à mão
- [ ] Rodar o sistema no mesmo vídeo
- [ ] Comparar: os cortes do sistema batem com os que ele escolheu? Quais ele NÃO teria pego? Quais ele pegou e o sistema perdeu?
- [ ] **Cronometrar:** quanto tempo ele leva pra finalizar 1 corte **com** o sistema vs **sem**
- [ ] **Taxa de aceite:** de 10 cortes do sistema, quantos ele realmente usaria?

## Etapa 3 — Produção + CutPro

- [ ] `python3 src/produzir.py <video_id> --top 5` → gera clipe + legenda + ficha + capa
- [ ] Jogar o clipe no CutPro e ver o acabamento
- [ ] Testar `python3 src/reframe.py <clipe.mp4>` → o vertical segue o rosto?

## Etapa 4 — Publicar e fechar o loop

- [ ] Publicar alguns cortes
- [ ] `python3 src/publicacoes.py registrar <src_id> <cut_id> <url_do_short>`
- [ ] Depois de uns dias: `publicacoes.py atualizar` + `performance.py` → o sistema começa a aprender o que performou

---

## O que medir (os números que provam tudo)

| Métrica | Como | Prova o quê |
|---|---|---|
| **Tempo por corte** (antes vs depois) | cronômetro na Etapa 2 | o ganho de tempo (a hipótese dos "30 min") |
| **Taxa de aceite** | % dos cortes do sistema que o Gustavo usa | a qualidade do critério |
| **Custo real por vídeo** | gasto de API por run | confirma o ~R$1–3 |
| **Gustavo topa o fluxo?** | feedback dele | a adoção (o gargalo sociológico) |

Esses 4 números dizem se o sistema entrega o que promete. **Sem eles, é tudo hipótese.** Com eles, vira fato — e aí a gente melhora com dado real, não no escuro.
