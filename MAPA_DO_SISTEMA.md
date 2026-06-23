# Mapa do Sistema — Operação de Cortes Cariani

Visão geral pra alinhar com o Mauricião e com o pessoal do CutPro. O que é, o que já está pronto, quanto custa e o que falta.

---

## O que é, em uma frase

Um sistema que pega os vídeos e lives do Renato, **descobre o que está em alta**, acha no acervo **o momento exato** que fala disso, **gera o corte** (com título, legenda e capa) e **aprende com a performance** — pra alimentar os canais sem ele gravar mais nada.

---

## As duas metades (e onde o CutPro entra)

- **O CÉREBRO (o que construímos):** decide *o quê, por quê e qual* — qual vídeo, qual momento, no tom certo, seguro, no que está em alta.
- **As MÃOS (o CutPro):** pega o trecho que o cérebro escolheu e faz o acabamento rápido (corte, legenda, formato).

> Hoje o CutPro corta "às cegas" (sem critério Cariani, sem tema em alta, sem voz). Nosso sistema entrega pra ele **o momento certo já pré-cortado** → ele só finaliza. Juntos: qualidade na quantidade.

---

## Onde estamos (níveis)

| Nível | Status |
|---|---|
| Caminho 1 — manual + planilha | descartado (não resolvia tempo) |
| Caminho 2 — IA marca os trechos (MVP) | ✅ **feito e testado** |
| Caminho 3 — sistema completo (rotina, métricas, feedback) | ✅ **construído** |
| Além do plano (voz, lives, tendência real, performance, multi-formato) | ✅ **construído** |

**Capacidade:** além do nível mais fodão que tínhamos desenhado.
**Operação real:** ainda no começo — falta indexar o acervo todo, transcrever e validar com o Gustavo. *(A Ferrari está montada; falta colocar na rua.)*

---

## O que o sistema faz hoje (por etapa)

**1. Captura e entende**
- Transcreve qualquer vídeo/live (aguenta horas) e identifica **quem fala pela voz** (Renato/Júlio/convidado).

**2. Critério de corte (o tom Cariani)**
- Acha **ideias completas** (gancho→desenvolvimento→fecho), no tom do personagem, com **trava anti-invenção** (só usa o que foi dito) e guardião de risco (caso PF, etc.).

**3. Inteligência (o que cortar hoje)**
- **Tendência real:** Google Trends + comentários do público + concorrentes BR.
- **Fila de oportunidade:** tema quente × material no acervo × tempo sem postar → "corta isso agora".
- **Buraco de conteúdo:** tema quente sem material → "grava isso".
- **Garimpo nas lives:** acha o tema dentro de uma live de horas, no minuto exato.
- **Calendário automático:** propõe a grade da semana.

**4. Produção (saída pro CutPro)**
- Gera o **MP4 do trecho** + **legenda (SRT)** + **ficha** (capa/título/copy) + **frame de capa** sugerido (visão).
- **Multi-formato:** 1 corte vira Reels + TikTok + Short + carrossel + thread + newsletter.

**5. Aprendizado**
- **Loop de performance:** puxa views/likes reais dos cortes publicados e re-prioriza o que o algoritmo já provou que funciona.
- **Cérebro do Renato:** pergunte "o que ele pensa sobre X" → resposta com citação e timestamp.

---

## Custos (honesto)

| Item | Custo |
|---|---|
| Cortar 1 vídeo (transcrever + analisar) | ~R$ 1–3 |
| Tendência do dia | ~R$ 0,10/dia (~R$ 3/mês) |
| Toda a inteligência, produção e aprendizado | **R$ 0** (roda local / cota grátis) |
| Transcrever o acervo de lives de conteúdo (uma vez) | ~R$ 233 |

O gasto é dominado pelo corte por vídeo (você controla pelo volume). O resto é praticamente grátis.

---

## Impacto esperado

- **Estoque:** transcrever as lives de conteúdo = **milhares de cortes** prontos pra puxar — anos de conteúdo sem gravar nada novo.
- **Ritmo:** de ~80 cortes/mês (hoje, manual) para **10–15/dia por editor** só com o sistema, e **25–40/dia** com o CutPro no acabamento. O gargalo deixa de ser "achar o que cortar" e vira "quantas mãos editam".

---

## O que falta (operacional, não é mais código)

1. Rodar a **indexação completa** do acervo (no Mac do time).
2. **Mauricião:** aprovar a transcrição em massa (~R$233).
3. **CutPro:** confirmar como recebe o clipe (a integração via pré-corte já está pronta do nosso lado).
4. **Gustavo:** validar com vídeos que ele conhece e medir o tempo real por corte.
5. Detalhes: URL real dos canais YouTube da Tati e do Júlio; trocar as chaves de API por segurança.
