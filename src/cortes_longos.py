"""SKILL ISOLADA — Cortes LONGOS (estilo podcast). Setor Balestrin por padrão.

TOTALMENTE separada do fluxo de cortes curtos do Renato:
  - prompt próprio (prompts/system_analyze_longo.md)
  - verificador próprio, SEM o cap de 150s (alvo 6–20 min)
  - store próprio: data/cuts_<setor>/  (não polui o painel do Renato)

Reutiliza só as peças neutras: download, transcribe, youtube_meta e os
ajudantes de casamento de texto do verify (_index/_achar/_fmt).

Config do setor em setores.json (canais-fonte, persona, perfil de duração).

Uso:
    python3 src/cortes_longos.py <url> --setor balestrin
"""
import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
from anthropic import Anthropic

from download import baixar_audio
from transcribe import transcrever, transcricao_para_texto_com_timestamps
from youtube_meta import metadados
from verify import _index, _achar, _fmt   # ajudantes neutros de casamento de texto

ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = ROOT / "prompts"
SETORES_PATH = ROOT / "setores.json"
DATA_DIR = Path(os.environ.get("DATA_DIR", "./data"))
AUDIO_DIR = DATA_DIR / "audio"
TRANSC_DIR = DATA_DIR / "transcricoes"


# ----------------------------------------------------------- config do setor
def perfil(setor: str) -> dict:
    cfg = {}
    if SETORES_PATH.exists():
        try:
            cfg = json.loads(SETORES_PATH.read_text(encoding="utf-8")).get(setor, {})
        except Exception:
            cfg = {}
    p = cfg.get("perfil_corte", {})
    dur_min = int(p.get("dur_min_seg", 300))          # alvo mínimo dito pra IA (5 min)
    return {
        "persona": cfg.get("persona", "julio"),
        "dur_min": dur_min,
        "dur_floor": int(p.get("dur_floor_seg", dur_min)),  # piso DURO do verificador
        "dur_max": int(p.get("dur_max_seg", 1200)),   # 20 min
        "nome": cfg.get("nome", setor),
    }


# ----------------------------------------------------------- análise (longa)
def _system_longo(persona_nome: str) -> str:
    base = (PROMPTS_DIR / "system_analyze_longo.md").read_text(encoding="utf-8")
    persona = (PROMPTS_DIR / f"persona_{persona_nome}.md").read_text(encoding="utf-8")
    return base.replace("{PERSONA_DOC}", persona)


def analisar_longo(texto_ts, persona_nome, video_id, video_title="", temas=None,
                   dur_min=360, dur_max=1200) -> dict:
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
    system = _system_longo(persona_nome)
    user = f"""# Vídeo
- ID: {video_id}
- Título: {video_title}
- Personagem-alvo: {persona_nome}
- Duração-alvo do corte: {dur_min // 60}–{dur_max // 60} minutos (corte LONGO de podcast)

# Temas em alta (use no scoring)
{json.dumps(temas or [], ensure_ascii=False)}

# Transcrição timestampada
{texto_ts}

---
Selecione os melhores BLOCOS LONGOS conforme as regras e devolva SÓ o JSON."""
    msg = client.messages.create(model=model, max_tokens=16000, system=system,
                                 messages=[{"role": "user", "content": user}])
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw.lstrip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return json.loads(raw)


# ----------------------------------------------------------- verificador (longo)
def verificar_longo(cuts, segments, dur_min=300, dur_max=1200, dur_floor=None):
    """Ancorar fronteira real, rejeitar invenção/curto-demais, fundir sobrepostos.
    SEM cap de 150s — aqui o corte é longo de propósito.
    dur_floor = piso DURO (rejeita abaixo). Se None, cai no próprio dur_min."""
    full, char2seg = _index(segments)
    if dur_floor is None:
        dur_floor = dur_min          # piso = alvo mínimo (sem tolerância surpresa)
    aprovados, rejeitados = [], []

    for c in cuts:
        ab = c.get("frase_abertura") or c.get("evidencia_literal") or ""
        fe = c.get("frase_fecho") or ""
        la = _achar(ab, full, char2seg, segments)
        if la is None:
            c["motivo_rejeicao"] = "abertura não encontrada (provável invenção)"
            c["fidelidade"] = 0.0
            rejeitados.append(c); continue
        lf = _achar(fe, full, char2seg, segments) if fe else None
        s_idx = la[0]
        e_idx = lf[1] if lf else la[1]
        if e_idx < s_idx:
            e_idx = la[1]; lf = None
        start = segments[s_idx]["start"]
        end = segments[e_idx]["end"]
        if end - start > dur_max:                  # estourou o teto: trava no máximo
            end = start + dur_max
            cands = [j for j, sg in enumerate(segments) if sg["start"] <= end]
            e_idx = max(cands) if cands else e_idx
            c["flag"] = c.get("flag") or "revisao"
        dur = end - start
        if dur < dur_floor:                        # curto demais pro setor longo
            c["motivo_rejeicao"] = f"curto pro setor longo ({dur:.0f}s < {dur_floor}s)"
            rejeitados.append(c); continue

        c["start_seconds"] = round(start, 1)
        c["end_seconds"] = round(end, 1)
        c["duration_seconds"] = round(dur, 1)
        c["start_timestamp"] = _fmt(start)
        c["end_timestamp"] = _fmt(end)
        c["transcricao_trecho"] = " ".join(segments[j]["text"].strip() for j in range(s_idx, e_idx + 1))
        c["fidelidade"] = min(la[2], lf[2] if lf else la[2])
        c["tipo_corte"] = "bloco_longo"
        c["formato"] = "longo"
        c["_s"], c["_e"] = s_idx, e_idx
        if c["fidelidade"] < 0.85:
            c["flag"] = c.get("flag") or "revisao"
        aprovados.append(c)

    # fusão de blocos sobrepostos (mesmo assunto picado)
    aprovados.sort(key=lambda x: (x["_s"], -x.get("score", 0)))
    fundidos = []
    for c in aprovados:
        merged = False
        for f in fundidos:
            if c["_s"] <= f["_e"] and c["_e"] >= f["_s"]:
                s = min(f["_s"], c["_s"]); e = max(f["_e"], c["_e"])
                forte = f if f.get("score", 0) >= c.get("score", 0) else c
                for k in ("score", "pilar_primario", "title_sugerido", "headline_post",
                          "copy_short_sugerida", "justificativa_score"):
                    if k in forte:
                        f[k] = forte[k]
                f["_s"], f["_e"] = s, e
                f["start_seconds"] = round(segments[s]["start"], 1)
                f["end_seconds"] = round(segments[e]["end"], 1)
                f["duration_seconds"] = round(f["end_seconds"] - f["start_seconds"], 1)
                f["start_timestamp"] = _fmt(f["start_seconds"]); f["end_timestamp"] = _fmt(f["end_seconds"])
                f["transcricao_trecho"] = " ".join(segments[j]["text"].strip() for j in range(s, e + 1))
                merged = True; break
        if not merged:
            fundidos.append(c)
    # re-aplica o TETO depois da fusão (blocos fundidos podiam estourar dur_max)
    for f in fundidos:
        if f["end_seconds"] - f["start_seconds"] > dur_max:
            novo_end = f["start_seconds"] + dur_max
            cands = [j for j, sg in enumerate(segments) if sg["start"] <= novo_end]
            e = max(cands) if cands else f["_e"]
            f["_e"] = e
            f["end_seconds"] = round(segments[e]["end"], 1)
            f["duration_seconds"] = round(f["end_seconds"] - f["start_seconds"], 1)
            f["end_timestamp"] = _fmt(f["end_seconds"])
            f["transcricao_trecho"] = " ".join(segments[j]["text"].strip() for j in range(f["_s"], e + 1))
            f["flag"] = f.get("flag") or "revisao"
    for c in fundidos:
        c.pop("_s", None); c.pop("_e", None)
    fundidos.sort(key=lambda x: x.get("score", 0), reverse=True)
    return fundidos, rejeitados


# ----------------------------------------------------------- store próprio
def _salvar(setor, res, video_id):
    cuts_dir = DATA_DIR / f"cuts_{setor}"
    cuts_dir.mkdir(parents=True, exist_ok=True)
    (cuts_dir / f"{video_id}.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    # índice do setor (separado do Renato)
    idx = {"setor": setor, "generated_at": datetime.utcnow().isoformat() + "Z", "cuts": []}
    for f in cuts_dir.glob("*.json"):
        if f.name.startswith("index"):
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        meta = d.get("video_meta", {})
        for c in d.get("cuts", []):
            idx["cuts"].append({
                "video_id": d.get("video_id", f.stem), "video_title": meta.get("title", ""),
                "headline_post": c.get("headline_post", ""), "score": c.get("score", 0),
                "duration_seconds": c.get("duration_seconds", 0),
                "start_timestamp": c.get("start_timestamp", ""),
                "provavel_falante": c.get("provavel_falante", ""),
            })
    idx["cuts"].sort(key=lambda x: x.get("score", 0), reverse=True)
    (cuts_dir / "index.json").write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")


# ----------------------------------------------------------- pipeline
def rodar(url, setor="balestrin", temas=None):
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    TRANSC_DIR.mkdir(parents=True, exist_ok=True)
    p = perfil(setor)
    print(f"=== SETOR {p['nome']} · cortes LONGOS {p['dur_floor']//60}-{p['dur_max']//60}min · persona {p['persona']} ===")

    print("[1/4] metadados")
    meta = metadados(url); vid = meta["video_id"]
    print(f"      {meta['title']} ({meta.get('channel','')})")

    print("[2/4] áudio")
    ai = baixar_audio(url, str(AUDIO_DIR))

    print("[3/4] transcrição")
    tp = TRANSC_DIR / f"{vid}.json"
    if tp.exists():
        transc = json.loads(tp.read_text(encoding="utf-8"))
        print("      (reutilizando transcrição em cache)")
    else:
        transc = transcrever(ai["path"])
        tp.write_text(json.dumps(transc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"      {len(transc['segments'])} segments")

    print("[4/4] análise LONGA (Claude)")
    texto = transcricao_para_texto_com_timestamps(transc)
    # loop de aprendizado: se já analisamos o canal de referência (analise_canal.py),
    # as palavras que MAIS performam lá entram como tema-bônus no scoring.
    temas_final = list(temas or [])
    ref = DATA / "setores" / f"{setor}_referencia.json"
    if ref.exists():
        try:
            perf = json.loads(ref.read_text(encoding="utf-8"))
            campeas = [w["palavra"] for w in perf.get("palavras_que_performam", [])[:8]]
            if campeas:
                temas_final = list(dict.fromkeys(temas_final + campeas))
                print(f"      ↳ realimentando do canal de referência: {', '.join(campeas)}")
        except Exception:
            pass
    res = analisar_longo(texto, p["persona"], vid, meta["title"], temas_final, p["dur_min"], p["dur_max"])
    aprov, rej = verificar_longo(res.get("cuts", []), transc["segments"],
                                 p["dur_min"], p["dur_max"], p["dur_floor"])
    res["cuts"] = aprov; res["rejeitados"] = rej
    res["person"] = p["persona"]; res["setor"] = setor
    res["video_id"] = vid; res["video_meta"] = meta
    res["processed_at"] = datetime.utcnow().isoformat() + "Z"

    _salvar(setor, res, vid)
    print(f"\n✓ {len(aprov)} cortes LONGOS salvos em data/cuts_{setor}/{vid}.json  ({len(rej)} rejeitados)")
    if aprov:
        for c in aprov[:5]:
            print(f"   [{c.get('score')}] {c['start_timestamp']}–{c['end_timestamp']} "
                  f"({c['duration_seconds']/60:.1f}min) {c.get('headline_post','')[:50]}")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Cortes LONGOS (setor) — isolado do fluxo curto")
    ap.add_argument("url", help="URL do episódio (IRONCAST/live/podcast)")
    ap.add_argument("--setor", default="balestrin")
    ap.add_argument("--temas", default="")
    a = ap.parse_args()
    temas = [t.strip() for t in a.temas.split(",") if t.strip()]
    rodar(a.url, a.setor, temas)
