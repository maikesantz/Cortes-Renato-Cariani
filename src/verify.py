"""Verificador de fidelidade e fronteira dos cortes (v2).

Para cada corte gerado pela IA:
  1. localiza `frase_abertura` e `frase_fecho` DENTRO dos segments reais;
  2. monta a fronteira real do corte (início da ideia -> fim da ideia) e
     reconstrói `transcricao_trecho` a partir dos segments — não confia no texto do modelo;
  3. mede fidelidade (0–1). Sem correspondência real -> corte INVENTADO (rejeitado);
  4. funde cortes sobrepostos (mesma ideia picada em pedaços);
  5. classifica tese_completa vs soundbite por duração/desenvolvimento.
"""
import re, difflib

MIN_TESE = 18      # segundos: abaixo disso não é "tese completa"
MAX_CORTE = 150    # segundos: acima disso provavelmente pegou dois assuntos


def _norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())).strip()


def _index(segments):
    full, char2seg = [], []
    for i, seg in enumerate(segments):
        t = _norm(seg["text"])
        if not t:
            continue
        if full:
            full.append(" "); char2seg.append(i)
        for _ in t:
            char2seg.append(i)
        full.append(t)
    return "".join(full), char2seg


def _achar(frase, full, char2seg, segments):
    """Retorna (seg_idx_inicio, seg_idx_fim, fidelidade) ou None."""
    alvo = _norm(frase)
    if not alvo or len(alvo) < 4:
        return None
    pos = full.find(alvo)
    if pos >= 0:
        return char2seg[pos], char2seg[min(pos + len(alvo) - 1, len(char2seg) - 1)], 1.0
    best_r, best = 0.0, None
    step = max(1, len(alvo) // 4)
    for i in range(0, max(1, len(full) - len(alvo) + 1), step):
        r = difflib.SequenceMatcher(None, alvo, full[i:i + len(alvo)]).ratio()
        if r > best_r:
            best_r, best = r, (i, i + len(alvo) - 1)
    if best and best_r >= 0.6:
        return char2seg[best[0]], char2seg[min(best[1], len(char2seg) - 1)], round(best_r, 2)
    return None


def _fmt(x):
    h = int(x // 3600); m = int((x % 3600) // 60); s = int(x % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def verificar_e_corrigir(cuts, segments):
    full, char2seg = _index(segments)
    candidatos, rejeitados = [], []

    for c in cuts:
        ab = c.get("frase_abertura") or c.get("evidencia_literal") or c.get("transcricao_trecho") or ""
        fe = c.get("frase_fecho") or ""
        la = _achar(ab, full, char2seg, segments)
        if la is None:
            c["motivo_rejeicao"] = "abertura não encontrada na transcrição (provável invenção)"
            c["fidelidade"] = 0.0
            rejeitados.append(c); continue
        lf = _achar(fe, full, char2seg, segments) if fe else None

        s_idx = la[0]
        e_idx = lf[1] if lf else la[1]
        if e_idx < s_idx:               # fecho antes da abertura -> usa só a abertura
            e_idx = la[1]; lf = None
        start = segments[s_idx]["start"]
        end = segments[e_idx]["end"]
        # corte absurdamente longo: provavelmente pegou dois assuntos -> trava no máximo
        if end - start > MAX_CORTE:
            end = start + MAX_CORTE
            _cands = [j for j, sg in enumerate(segments) if sg["start"] <= end]
            e_idx = max(_cands) if _cands else e_idx
            c["flag"] = c.get("flag") or "revisao"

        trecho = " ".join(segments[j]["text"].strip() for j in range(s_idx, e_idx + 1))
        fid = min(la[2], lf[2] if lf else la[2])

        c["start_seconds"] = round(start, 1)
        c["end_seconds"] = round(end, 1)
        c["duration_seconds"] = round(end - start, 1)
        c["start_timestamp"] = _fmt(start)
        c["end_timestamp"] = _fmt(end)
        c["transcricao_trecho"] = trecho
        c["fidelidade"] = fid
        c["_s_idx"], c["_e_idx"] = s_idx, e_idx
        if c["duration_seconds"] < 8:          # menos que isso é frase solta, sem arco
            c["motivo_rejeicao"] = f"curto/sem contexto ({c['duration_seconds']:.0f}s) — não é corte postável"
            rejeitados.append(c)
            continue
        if fid < 0.85:
            c["flag"] = c.get("flag") or "revisao"
        candidatos.append(c)

    # --- fusão de cortes sobrepostos (mesma ideia picada) ---
    candidatos.sort(key=lambda x: (x["_s_idx"], -x.get("score", 0)))
    fundidos = []
    for c in candidatos:
        merged = False
        for f in fundidos:
            # sobreposição de índices de segmento
            if c["_s_idx"] <= f["_e_idx"] and c["_e_idx"] >= f["_s_idx"]:
                # une fronteiras, mantém maior score e metadados do mais forte
                s_idx = min(f["_s_idx"], c["_s_idx"]); e_idx = max(f["_e_idx"], c["_e_idx"])
                forte = f if f.get("score", 0) >= c.get("score", 0) else c
                f.update({k: forte[k] for k in ("score", "pilar_primario", "title_sugerido",
                          "headline_post", "copy_short_sugerida", "evidencia_literal",
                          "justificativa_score", "bordao_presente") if k in forte})
                f["_s_idx"], f["_e_idx"] = s_idx, e_idx
                f["start_seconds"] = round(segments[s_idx]["start"], 1)
                f["end_seconds"] = round(segments[e_idx]["end"], 1)
                f["duration_seconds"] = round(f["end_seconds"] - f["start_seconds"], 1)
                f["start_timestamp"] = _fmt(f["start_seconds"]); f["end_timestamp"] = _fmt(f["end_seconds"])
                f["transcricao_trecho"] = " ".join(segments[j]["text"].strip() for j in range(s_idx, e_idx + 1))
                f["fundido"] = f.get("fundido", 1) + 1
                merged = True
                break
        if not merged:
            fundidos.append(c)

    # --- classificação final ---
    for c in fundidos:
        dur = c["duration_seconds"]
        c["tipo_corte"] = "tese_completa" if dur >= MIN_TESE else "soundbite"
        c["publicavel_sozinho"] = dur >= 15   # abaixo disso: só story/combinado, não Reels solto
        if c.get("tipo_corte") == "tese_completa" and not c.get("frase_fecho"):
            c["flag"] = c.get("flag") or "revisao"
        for k in ("_s_idx", "_e_idx"):
            c.pop(k, None)

    fundidos.sort(key=lambda x: x.get("score", 0), reverse=True)
    return fundidos, rejeitados
