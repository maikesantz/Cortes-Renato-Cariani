"""Persona por falante — corrige o TOM dos cortes de convidado.

Em podcast/treino com convidado, a análise roda com a persona do alvo (ex.: renato), mas a
voz pode revelar que quem fala é outro (ex.: julio). Aqui a gente re-escreve título, capa e
copy desses cortes no tom do falante REAL (usando a persona dele), sem mexer no trecho/timestamp.

Depende do speaker_id (campo falante_voz, já gravado pelo main.py) e de existir prompts/persona_<falante>.md.

Uso: python3 src/repersona.py <video_id>
"""
import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
ROOT = Path(__file__).parent.parent
DATA = Path(os.environ.get("DATA_DIR", "./data"))
PROMPTS = ROOT / "prompts"


def _persona_existe(nome):
    return (PROMPTS / f"persona_{nome}.md").exists()


def reescrever(video_id):
    cuts_path = DATA / "cuts" / f"{video_id}.json"
    if not cuts_path.exists():
        print("Sem cortes pra", video_id); return
    data = json.loads(cuts_path.read_text(encoding="utf-8"))
    alvo = data.get("person", "")
    cuts = data.get("cuts", [])

    # agrupa cortes por falante real (voz) que tem persona própria e != alvo
    por_falante = {}
    for c in cuts:
        f = c.get("falante_voz")
        if f and f != alvo and f not in ("não identificado", "sem_referencia", "erro_audio") and _persona_existe(f):
            por_falante.setdefault(f, []).append(c)

    if not por_falante:
        print("Nenhum corte de convidado com persona própria — nada a reescrever.")
        return

    from anthropic import Anthropic
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

    for falante, grupo in por_falante.items():
        persona = (PROMPTS / f"persona_{falante}.md").read_text(encoding="utf-8")
        itens = [{"id": c.get("id"), "trecho": c.get("transcricao_trecho", "")[:500]} for c in grupo]
        prompt = (f"Estes trechos são falados por {falante.upper()}. Reescreva 3 campos NO TOM DELE, fiel ao que foi dito (não invente).\n\n"
                  f"# Persona de {falante}\n{persona}\n\n"
                  "FORMATO DE CADA CAMPO (siga à risca):\n"
                  "- title_sugerido: título curto (máx 80 chars), tom do personagem.\n"
                  "- headline_post: CAPA em CAIXA ALTA, curta e de impacto, com 1-3 palavras-chave entre *asteriscos* "
                  "(vão em vermelho). Ex.: \"NINGUÉM CRESCE *SOZINHO* — A VERDADE SOBRE *PARCERIA*\". NÃO é frase falada.\n"
                  "- copy_short_sugerida: 1-2 frases no tom falado do personagem.\n\n"
                  "Responda APENAS JSON: [{\"id\":N,\"title_sugerido\":\"...\",\"headline_post\":\"CAIXA ALTA com *destaque*\",\"copy_short_sugerida\":\"...\"}]\n\n"
                  f"Trechos:\n{json.dumps(itens, ensure_ascii=False)}")
        msg = client.messages.create(model=model, max_tokens=3000, messages=[{"role": "user", "content": prompt}])
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]; raw = raw[4:] if raw.startswith("json") else raw; raw = raw.rsplit("```", 1)[0]
        try:
            novos = {n["id"]: n for n in json.loads(raw)}
        except Exception as e:
            print(f"  falha ao reescrever {falante}: {str(e)[:60]}"); continue
        n = 0
        for c in grupo:
            nv = novos.get(c.get("id"))
            if nv:
                c["title_sugerido"] = nv.get("title_sugerido", c.get("title_sugerido"))
                c["headline_post"] = nv.get("headline_post", c.get("headline_post"))
                c["copy_short_sugerida"] = nv.get("copy_short_sugerida", c.get("copy_short_sugerida"))
                c["persona_aplicada"] = falante
                n += 1
        print(f"  {falante}: {n} corte(s) reescrito(s) no tom certo")

    cuts_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    # regenera index.js pro dashboard
    sys.path.insert(0, str(ROOT / "src"))
    import main as M
    M.atualizar_index(data, video_id)
    print("✓ atualizado")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 src/repersona.py <video_id>"); sys.exit(1)
    reescrever(sys.argv[1])
