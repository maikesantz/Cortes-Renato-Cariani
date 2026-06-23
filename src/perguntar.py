"""Cérebro do Renato — pergunte qualquer coisa sobre o que ele já disse.

Busca a pergunta nas transcrições (o que ele REALMENTE falou), e o Claude responde usando
SÓ esses trechos, com citação (vídeo + timestamp). Copiloto interno: "o que o Renato pensa
sobre X?" → resposta fundamentada nas palavras dele, não em invenção.

Quanto mais lives transcritas, mais ele sabe. Rodar:
    python3 src/perguntar.py "o Renato é a favor de jejum intermitente?"
"""
import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))
import busca_transcricao as bt


def perguntar(pergunta, top=8):
    hits = bt.buscar(pergunta, top=top, min_sim=0.25)
    if not hits:
        print("Não achei nada sobre isso nas transcrições atuais.")
        print("(Transcreva mais lives com transcrever_lote.py pra ele saber mais.)")
        return

    contexto = [{"fonte": f"{h['video_id']}@{h['ts']}", "fala": h["trecho"]} for h in hits]
    from anthropic import Anthropic
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
    prompt = (
        "Responda a pergunta USANDO SOMENTE os trechos reais abaixo (o que o Renato Cariani disse). "
        "Não invente nada fora deles. Cite a fonte (vídeo@timestamp) ao afirmar algo. Se os trechos "
        "não respondem, diga claramente que o acervo transcrito ainda não cobre isso.\n\n"
        f"PERGUNTA: {pergunta}\n\n"
        f"TRECHOS REAIS:\n{json.dumps(contexto, ensure_ascii=False, indent=1)}"
    )
    msg = client.messages.create(model=model, max_tokens=700, messages=[{"role": "user", "content": prompt}])
    print(msg.content[0].text.strip())
    print("\n— fontes:")
    for h in hits[:5]:
        print(f"   {h['video_id']} @ {h['ts']}  (sim {h['sim']})")


if __name__ == "__main__":
    q = " ".join(sys.argv[1:])
    if not q:
        print('Uso: python3 src/perguntar.py "sua pergunta"'); sys.exit(1)
    perguntar(q)
