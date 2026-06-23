"""Calendário automático — o sistema propõe a grade da semana.

Pega a fila de oportunidade (o que cortar, ranqueado) + os buracos (o que gravar) e distribui
em 7 dias, nos horários de pico, sem repetir tema. É o passo de "o sistema planeja, o humano
aprova" — sai do corte avulso pra estratégia da semana.

Os pesos de performance (performance.py) afinam o que sobe na fila quando você de fato corta
(main.py aplica o fator). Aqui a régua é a oportunidade (tema quente × material × janela).

Rodar: python3 src/calendario.py            (usa os temas/oportunidade do dia)
       python3 src/calendario.py --slots 3  (3 cortes por dia)
"""
import os
import sys
import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))
from oportunidade import analisar

DATA = Path(os.environ.get("DATA_DIR", "./data"))
DIAS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
HORARIOS = ["18h", "12h", "20h"]   # pico primeiro (base: Insights — 18h é o ouro)


def montar(slots_por_dia=2, dias=7, person=None):
    cortar, gravar = analisar(person=person)
    fila = []
    for c in cortar:
        if c.get("top"):
            v = c["top"][0][1]
            fila.append({"tema": c["tema"], "opp": c["opp"], "video": v, "gap": c.get("gap")})

    hoje = datetime.date.today()
    plano, idx = [], 0
    for d in range(dias):
        data = hoje + datetime.timedelta(days=d)
        slots = []
        for h in HORARIOS[:slots_por_dia]:
            if idx < len(fila):
                slots.append((h, fila[idx])); idx += 1
        plano.append((data, slots))
    return plano, gravar, len(fila)


def relatorio(slots_por_dia=2, person=None):
    plano, gravar, total = montar(slots_por_dia, person=person)
    L = [f"# Grade da semana — proposta automática", f"_gerada em {datetime.date.today():%d/%m/%Y}_\n"]
    if total == 0:
        L.append("_Fila de oportunidade vazia — rode `briefing.py`/`oportunidade.py` antes "
                 "(e indexe mais do acervo pra encher a fila)._")
    for data, slots in plano:
        dia = DIAS[data.weekday()]
        L.append(f"\n### {dia} {data:%d/%m}")
        if not slots:
            L.append("- _(sem corte agendado — fila acabou; transcreva/indexe mais pra encher)_")
        for h, item in slots:
            v = item["video"]
            L.append(f"- **{h}** · {item['tema']} (oport {item['opp']}) — *{v['title'][:46]}*")
            L.append(f"    `python3 src/main.py \"https://youtube.com/watch?v={v['video_id']}\" --person {person or 'renato'}`")

    if gravar:
        L.append("\n## 🎥 Gravar nesta semana (temas quentes sem material)")
        for g in gravar[:4]:
            L.append(f"- **{g['tema']}** ({g.get('nivel')}) — {g.get('motivo','')[:80]}")

    L.append("\n_Regra: 18h é o horário ouro; 12h e 20h secundários. Performance (performance.py) "
             "afina quais cortes do tema sobem quando você processa._")

    out = DATA / "relatorios"
    out.mkdir(parents=True, exist_ok=True)
    caminho = out / f"calendario_{datetime.date.today():%Y-%m-%d}.md"
    caminho.write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))
    print(f"\n[salvo em {caminho}]")


if __name__ == "__main__":
    slots = 2
    if "--slots" in sys.argv:
        slots = int(sys.argv[sys.argv.index("--slots") + 1])
    relatorio(slots_por_dia=slots)
