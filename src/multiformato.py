"""Multi-formato — 1 corte vira várias peças, cada uma no algoritmo da plataforma.

De um corte (trecho + tom do personagem), gera: legenda de Reels, de TikTok, título de Short,
carrossel (slides), thread e trecho de newsletter. Fiel ao que foi dito (não inventa).
Um corte = uma chamada Claude (~centavos). Opcional, roda nos cortes que você quer espalhar.

Uso:
    python3 src/multiformato.py <video_id>           # top cortes do vídeo
    python3 src/multiformato.py <video_id> --top 3
"""
import os
import sys
import json
import argparse
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
ROOT = Path(__file__).parent.parent
DATA = Path(os.environ.get("DATA_DIR", "./data"))
sys.path.insert(0, str(ROOT / "src"))


def _persona(person):
    f = ROOT / "prompts" / f"persona_{person}.md"
    return f.read_text(encoding="utf-8")[:1500] if f.exists() else ""


def gerar(cut, person):
    from anthropic import Anthropic
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
    prompt = (
        f"Você adapta UM corte do {person.title()} pra várias plataformas. Fiel ao que foi dito "
        "(não invente fato). Tom do personagem abaixo. Algoritmo 2026: máx 3 hashtags, CTA de "
        "salvar/compartilhar pesa, carrossel fecha com 'Salva esse post'.\n\n"
        f"# Tom de {person}\n{_persona(person)}\n\n"
        f"# Corte (fala real)\n{cut.get('transcricao_trecho','')[:700]}\n"
        f"# Tema/título: {cut.get('title_sugerido','')}\n\n"
        "Responda APENAS JSON:\n"
        "{\"reels\":{\"legenda\":\"1-2 linhas + CTA\",\"hashtags\":[\"#\",\"#\",\"#\"]},"
        "\"tiktok\":{\"legenda\":\"...\",\"hashtags\":[\"#\",\"#\",\"#\"]},"
        "\"short_titulo\":\"...\","
        "\"carrossel\":[\"slide 1 (gancho)\",\"slide 2\",\"slide 3\",\"Salva esse post\"],"
        "\"thread\":[\"tweet 1\",\"tweet 2\",\"tweet 3\"],"
        "\"newsletter\":\"um parágrafo curto\"}")
    msg = client.messages.create(model=model, max_tokens=1500, messages=[{"role": "user", "content": prompt}])
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        partes = raw.split("```"); raw = partes[1] if len(partes) > 1 else raw.lstrip("`")
        if raw.startswith("json"): raw = raw[4:]
        raw = raw.strip()
    return json.loads(raw)


def _markdown(c, f):
    rl, tk = f.get("reels", {}), f.get("tiktok", {})
    return (
        f"# Multi-formato — {c.get('title_sugerido','')}\n\n"
        f"**Reels** — {rl.get('legenda','')}\n{' '.join(rl.get('hashtags',[]))}\n\n"
        f"**TikTok** — {tk.get('legenda','')}\n{' '.join(tk.get('hashtags',[]))}\n\n"
        f"**Short (título):** {f.get('short_titulo','')}\n\n"
        f"**Carrossel:**\n" + "\n".join(f"  {i+1}. {s}" for i, s in enumerate(f.get('carrossel', []))) + "\n\n"
        f"**Thread:**\n" + "\n".join(f"  - {t}" for t in f.get('thread', [])) + "\n\n"
        f"**Newsletter:** {f.get('newsletter','')}\n"
    )


def rodar(video_id, top=3):
    cuts_path = DATA / "cuts" / f"{video_id}.json"
    if not cuts_path.exists():
        print("Sem cortes pra", video_id); return
    data = json.loads(cuts_path.read_text(encoding="utf-8"))
    person = data.get("person", "renato")
    cuts = sorted(data.get("cuts", []), key=lambda x: x.get("prioridade", x.get("score", 0)), reverse=True)[:top]
    destino = DATA / "clipes" / video_id
    destino.mkdir(parents=True, exist_ok=True)
    for c in cuts:
        if not c.get("transcricao_trecho"):
            continue
        try:
            f = gerar(c, c.get("persona_aplicada") or c.get("falante_voz") or person)
            out = destino / f"cut{c.get('id')}_{int(c.get('start_seconds',0))}-{int(c.get('end_seconds',0))}.formatos.md"
            out.write_text(_markdown(c, f), encoding="utf-8")
            print(f"  cut {c.get('id')}: {len(f.get('carrossel',[]))} slides, thread, reels/tiktok/newsletter → {out.name}")
        except Exception as e:
            print(f"  cut {c.get('id')} erro: {str(e)[:70]}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("video_id"); p.add_argument("--top", type=int, default=3)
    a = p.parse_args(); rodar(a.video_id, a.top)
