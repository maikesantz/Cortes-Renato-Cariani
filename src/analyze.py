"""Análise dos trechos via Claude (Anthropic).

Recebe transcrição timestampada + persona + temas em alta.
Devolve JSON de cortes rankeados.
"""

import os
import json
from pathlib import Path
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def carregar_persona(person: str) -> str:
    """Carrega o markdown da persona (renato, julio ou tati)."""
    arq = PROMPTS_DIR / f"persona_{person}.md"
    if not arq.exists():
        raise FileNotFoundError(f"Persona não encontrada: {arq}")
    return arq.read_text(encoding="utf-8")


def carregar_system_prompt(person: str) -> str:
    """Monta o system prompt com persona injetada."""
    base = (PROMPTS_DIR / "system_analyze.md").read_text(encoding="utf-8")
    persona = carregar_persona(person)
    return base.replace("{PERSONA_DOC}", persona)


def analisar(
    transcricao_texto: str,
    person: str,
    video_id: str,
    video_title: str = "",
    temas_alta: list = None,
) -> dict:
    """Manda transcrição timestampada pro Claude, recebe JSON de cortes."""
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
    temas_alta = temas_alta or []

    system = carregar_system_prompt(person)

    user_content = f"""# Vídeo
- ID: {video_id}
- Título: {video_title}
- Personagem: {person}

# Temas em alta no momento (use no scoring)
{json.dumps(temas_alta, ensure_ascii=False)}

# Transcrição timestampada
{transcricao_texto}

---
Aplique o critério Cariani sobre essa transcrição e devolva o JSON conforme as regras."""

    msg = client.messages.create(
        model=model,
        max_tokens=16000,
        system=system,
        messages=[{"role": "user", "content": user_content}]
    )

    raw = msg.content[0].text.strip()
    # remove cerca de código se tiver (robusto a cerca incompleta)
    if raw.startswith("```"):
        partes = raw.split("```")
        raw = partes[1] if len(partes) > 1 else raw.lstrip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        print("Erro decodificando JSON do Claude. Saída bruta:")
        print(raw[:2000])
        raise e

    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("Uso: python analyze.py <transcricao.txt> <person:renato|julio> <video_id>")
        sys.exit(1)
    transc = Path(sys.argv[1]).read_text(encoding="utf-8")
    out = analisar(transc, sys.argv[2], sys.argv[3])
    print(json.dumps(out, indent=2, ensure_ascii=False))
