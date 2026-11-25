"""Gera a planilha de avaliação do TCC (cronometragem e SUS).

Uso:
    python scripts/docs/gerar_avaliacao.py [saida.xlsx]

Saída padrão: docs/avaliacao/Planilha_Avaliacao_GalviTracks.xlsx
As células amarelas são para preencher; as demais são calculadas por fórmula.
"""

import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

RAIZ = Path(__file__).resolve().parents[2]
SAIDA = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "docs" / "avaliacao" / "Planilha_Avaliacao_GalviTracks.xlsx"

FONTE = "Arial"
ROXO = "401F71"
LAVANDA = "EFEAF6"
AMARELO = PatternFill("solid", fgColor="FFF2CC")  # células para preencher
CABECALHO = PatternFill("solid", fgColor=ROXO)
CINZA = PatternFill("solid", fgColor="F5F5F5")
FINA = Side(style="thin", color="D4D4D4")
BORDA = Border(left=FINA, right=FINA, top=FINA, bottom=FINA)

LINHA_INI = 5          # primeira linha de dados nas abas de medição
N_DESPACHOS = 60       # linhas para despachos em cada fase
N_SUS = 30             # linhas para respondentes do SUS
LINHA_FIM = LINHA_INI + N_DESPACHOS - 1
SUS_FIM = LINHA_INI + N_SUS - 1

PERGUNTAS_SUS = [
    "Eu acho que gostaria de usar este sistema com frequência.",
    "Eu achei o sistema desnecessariamente complexo.",
    "Eu achei o sistema fácil de usar.",
    "Eu acho que precisaria da ajuda de um técnico para conseguir usar este sistema.",
    "Eu achei que as várias funções deste sistema estão bem integradas.",
    "Eu achei que havia muita inconsistência neste sistema.",
    "Eu imagino que a maioria das pessoas aprenderia a usar este sistema rapidamente.",
    "Eu achei o sistema muito complicado de usar.",
    "Eu me senti muito confiante usando o sistema.",
    "Eu precisei aprender muitas coisas antes de conseguir usar este sistema.",
]

PERGUNTAS_MOTOBOY = [
    "Foi fácil instalar e configurar o OwnTracks no meu celular.",
    "Depois de configurado, não precisei mexer no aplicativo durante as entregas.",
    "O consumo de bateria do celular ficou aceitável.",
    "Receber a rota com as paradas em ordem ajudou nas entregas.",
]


def f(bold=False, cor="000000", tamanho=10, italico=False):
    return Font(name=FONTE, bold=bold, color=cor, size=tamanho, italic=italico)


def titulo(ws, texto, subtitulo):
    ws["A1"] = texto
    ws["A1"].font = f(True, ROXO, 14)
    ws["A2"] = subtitulo
    ws["A2"].font = f(cor="595959", italico=True)


def cabecalho(ws, linha, colunas):
    for i, (texto, largura) in enumerate(colunas, start=1):
        c = ws.cell(row=linha, column=i, value=texto)
        c.font = f(True, "FFFFFF")
        c.fill = CABECALHO
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BORDA
        ws.column_dimensions[get_column_letter(i)].width = largura
    ws.row_dimensions[linha].height = 32


def celula(ws, ref, valor=None, entrada=False, fmt=None, alinhar="left", negrito=False):
    c = ws[ref]
    if valor is not None:
        c.value = valor
    c.font = f(negrito)
    c.border = BORDA
    c.alignment = Alignment(horizontal=alinhar, vertical="center", wrap_text=True)
    if entrada:
        c.fill = AMARELO
    if fmt:
        c.number_format = fmt
    return c


# --- Abas de medição (base e piloto) ---
COLUNAS_MEDICAO = [
    ("Nº", 6), ("Data", 12), ("Operador", 16), ("Motoboy", 16), ("Nº de paradas", 10),
    ("Notas / pedidos", 18), ("Minutos", 9), ("Segundos", 9), ("Tempo total (min)", 12), ("Observações", 40),
]


def aba_medicao(wb, nome, titulo_aba, descricao):
    ws = wb.create_sheet(nome)
    titulo(ws, titulo_aba, descricao)
    ws["A3"] = "Preencha só as células amarelas. O tempo total é calculado (minutos + segundos ÷ 60)."
    ws["A3"].font = f(cor="595959", tamanho=9)
    cabecalho(ws, 4, COLUNAS_MEDICAO)
    validar_paradas = DataValidation(type="whole", operator="between", formula1="1", formula2="30",
                                     error="Informe um número de paradas entre 1 e 30.", showErrorMessage=True)
    validar_min = DataValidation(type="whole", operator="between", formula1="0", formula2="240",
                                 error="Minutos entre 0 e 240.", showErrorMessage=True)
    validar_seg = DataValidation(type="whole", operator="between", formula1="0", formula2="59",
                                 error="Segundos entre 0 e 59.", showErrorMessage=True)
    validar_data = DataValidation(type="date", operator="greaterThan", formula1="DATE(2026,1,1)",
                                  error="Informe uma data (dd/mm/aaaa).", showErrorMessage=True)
    for v in (validar_paradas, validar_min, validar_seg, validar_data):
        ws.add_data_validation(v)
    for r in range(LINHA_INI, LINHA_FIM + 1):
        celula(ws, f"A{r}", r - LINHA_INI + 1, alinhar="center")
        celula(ws, f"B{r}", entrada=True, fmt="dd/mm/yyyy", alinhar="center")
        celula(ws, f"C{r}", entrada=True)
        celula(ws, f"D{r}", entrada=True)
        celula(ws, f"E{r}", entrada=True, fmt="0", alinhar="center")
        celula(ws, f"F{r}", entrada=True)
        celula(ws, f"G{r}", entrada=True, fmt="0", alinhar="center")
        celula(ws, f"H{r}", entrada=True, fmt="0", alinhar="center")
        celula(ws, f"I{r}", f'=IF(AND(G{r}="",H{r}=""),"",N(G{r})+N(H{r})/60)', fmt="0.00", alinhar="center", negrito=True)
        celula(ws, f"J{r}", entrada=True)
    validar_data.add(f"B{LINHA_INI}:B{LINHA_FIM}")
    validar_paradas.add(f"E{LINHA_INI}:E{LINHA_FIM}")
    validar_min.add(f"G{LINHA_INI}:G{LINHA_FIM}")
    validar_seg.add(f"H{LINHA_INI}:H{LINHA_FIM}")
    ws.freeze_panes = f"A{LINHA_INI}"
    ws.print_title_rows = "4:4"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    return ws


# --- Leia-me ---
def aba_leiame(wb):
    ws = wb.active
    ws.title = "Leia-me"
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 95
    titulo(ws, "Avaliação do GalviTracks na Radar Auto Peças",
           "TCC Engenharia de Software · André Gustavo Specht · protocolo completo em docs/avaliacao/README.md")
    linhas = [
        ("O que medir", "O tempo de planejamento de um despacho: do momento em que o operador começa a organizar a "
                        "saída (pedidos/notas em mãos) até o motoboy ser liberado com a ordem das paradas definida."),
        ("Base (sem sistema)", "Do jeito atual (telefone, WhatsApp, de cabeça). Medir antes de usar o GalviTracks."),
        ("Piloto (com sistema)", "Com o GalviTracks: do início da montagem da rota no painel até o clique em "
                                 "\"Sair para entrega\"."),
        ("Como cronometrar", "Use o cronômetro do celular. Anote minutos e segundos nas colunas amarelas; o tempo "
                             "total em minutos é calculado sozinho."),
        ("Quantos despachos", "Meta: pelo menos 20 na base e 20 no piloto, em dias e horários parecidos."),
        ("SUS", "Questionário de usabilidade (Brooke, 1996). Imprima a aba \"SUS formulário\", aplique aos usuários do "
                "painel (operadores e gestor) no fim do piloto e digite as respostas (1 a 5) na aba \"SUS respostas\"."),
        ("Nota SUS", "0 a 100. Ímpares: resposta − 1; pares: 5 − resposta; soma × 2,5. Faixas de Bangor, Kortum e "
                     "Miller (2009): ≥ 85,5 excelente; ≥ 71,4 bom; ≥ 50,9 OK; ≥ 35,7 ruim. Meta do TCC: ≥ 71 (bom)."),
        ("Motoboys", "Opcional: 4 afirmações sobre o OwnTracks na aba \"Motoboys\", na mesma escala de 1 a 5."),
        ("Incidentes", "Anote na aba \"Incidentes\" tudo o que atrapalhou o piloto (sinal, internet, erro no painel)."),
    ]
    r = 4
    for rotulo, texto in linhas:
        ws.cell(row=r, column=1, value=rotulo).font = f(True, ROXO)
        c = ws.cell(row=r, column=2, value=texto)
        c.font = f()
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.cell(row=r, column=1).alignment = Alignment(vertical="top")
        ws.row_dimensions[r].height = 30 if len(texto) > 95 else 16
        r += 1
    ws.cell(row=r, column=1, value="Legenda").font = f(True, ROXO)
    exemplo_legenda = ws.cell(row=r, column=2, value="Amarelo = preencher. Branco = calculado por fórmula (não apagar).")
    exemplo_legenda.fill = AMARELO
    exemplo_legenda.font = f()

    r += 2
    ws.cell(row=r, column=1, value="Exemplo de linha preenchida").font = f(True, ROXO)
    r += 1
    exemplo = ["1", "26/11/2026", "Carlos", "Victor", "4", "NF 10231, 10235", "6", "40", "6,67", "Cliente pediu urgência"]
    # Exemplo como texto corrido (as colunas desta aba têm outras larguras)
    ws.cell(row=r, column=1, value="Colunas").font = f(True)
    ws.cell(row=r, column=2, value=" | ".join(c for c, _ in COLUNAS_MEDICAO)).font = f()
    ws.cell(row=r + 1, column=1, value="Valores").font = f(True)
    ws.cell(row=r + 1, column=2, value=" | ".join(exemplo)).font = f(italico=True)
    ws.cell(row=r + 2, column=2, value="(o tempo total 6,67 min = 6 min + 40 s; ele é calculado, não precisa digitar)").font = f(cor="595959", tamanho=9)
    ws.sheet_view.showGridLines = False


# --- Resumo ---
def aba_resumo(wb):
    ws = wb.create_sheet("Resumo")
    titulo(ws, "Resumo da avaliação", "Tudo nesta aba é calculado a partir das outras abas.")
    for col, larg in zip("ABCD", (40, 16, 16, 18)):
        ws.column_dimensions[col].width = larg
    cabecalho(ws, 4, [("Tempo de planejamento por despacho", 40), ("Base (sem sistema)", 16),
                      ("Piloto (com sistema)", 16), ("Redução (piloto vs. base)", 18)])
    faixa = lambda aba, col: f"'{aba}'!{col}{LINHA_INI}:{col}{LINHA_FIM}"  # noqa: E731
    base, piloto = "Base (sem sistema)", "Piloto (com sistema)"
    metricas = [
        ("Despachos medidos", "COUNT({t})", "0", False),
        ("Média (min)", 'IFERROR(AVERAGE({t}),"")', "0.00", True),
        ("Mediana (min)", 'IFERROR(MEDIAN({t}),"")', "0.00", True),
        ("Desvio padrão (min)", 'IFERROR(STDEV({t}),"")', "0.00", False),
        ("Menor tempo (min)", 'IF(COUNT({t})=0,"",MIN({t}))', "0.00", False),
        ("Maior tempo (min)", 'IF(COUNT({t})=0,"",MAX({t}))', "0.00", False),
        ("Paradas por despacho (média)", 'IFERROR(AVERAGE({p}),"")', "0.0", False),
        ("Tempo por parada (min)", 'IFERROR(SUMIFS({t},{p},">0")/SUMIFS({p},{t},">0"),"")', "0.00", True),
    ]
    r = 5
    for rotulo, formula, fmt, reduz in metricas:
        celula(ws, f"A{r}", rotulo, negrito=True)
        for col, aba in (("B", base), ("C", piloto)):
            celula(ws, f"{col}{r}", "=" + formula.format(t=faixa(aba, "I"), p=faixa(aba, "E")), fmt=fmt, alinhar="center")
        celula(ws, f"D{r}", f'=IFERROR(IF(OR(B{r}="",C{r}=""),"",(B{r}-C{r})/B{r}),"")' if reduz else "", fmt="0.0%", alinhar="center")
        r += 1
    ws[f"A{r}"] = "Redução positiva = o planejamento ficou mais rápido com o sistema."
    ws[f"A{r}"].font = f(cor="595959", tamanho=9, italico=True)

    r += 2
    cabecalho(ws, r, [("Usabilidade (SUS)", 40), ("Valor", 16), ("", 16), ("", 18)])
    sus = f"'SUS respostas'!N{LINHA_INI}:N{SUS_FIM}"
    linhas_sus = [
        ("Respondentes", f"=COUNT({sus})", "0"),
        ("Nota SUS média (0 a 100)", f'=IFERROR(AVERAGE({sus}),"")', "0.0"),
        ("Menor nota", f'=IF(COUNT({sus})=0,"",MIN({sus}))', "0.0"),
        ("Maior nota", f'=IF(COUNT({sus})=0,"",MAX({sus}))', "0.0"),
    ]
    r += 1
    linha_media = None
    for rotulo, formula, fmt in linhas_sus:
        celula(ws, f"A{r}", rotulo, negrito=True)
        celula(ws, f"B{r}", formula, fmt=fmt, alinhar="center")
        if rotulo.startswith("Nota SUS média"):
            linha_media = r
        r += 1
    celula(ws, f"A{r}", "Classificação (Bangor et al., 2009)", negrito=True)
    m = f"B{linha_media}"
    celula(ws, f"B{r}", f'=IF({m}="","",IF({m}>=85.5,"Excelente",IF({m}>=71.4,"Bom",IF({m}>=50.9,"OK",IF({m}>=35.7,"Ruim","Péssimo")))))', alinhar="center")
    r += 1
    celula(ws, f"A{r}", "Meta do TCC (nota ≥ 71) atingida?", negrito=True)
    celula(ws, f"B{r}", f'=IF({m}="","",IF({m}>=71,"Sim","Não"))', alinhar="center")
    ws[f"B{r}"].comment = Comment("Meta definida no projeto do TCC: escore SUS 'bom' ou superior (≥ 71).", "GalviTracks")
    r += 2
    cabecalho(ws, r, [("Motoboys (opcional, média de 1 a 5)", 40), ("Média", 16), ("", 16), ("", 18)])
    r += 1
    for i, pergunta in enumerate(PERGUNTAS_MOTOBOY):
        col = get_column_letter(4 + i)
        celula(ws, f"A{r}", pergunta)
        celula(ws, f"B{r}", f"=IFERROR(AVERAGE(Motoboys!{col}{LINHA_INI}:{col}{LINHA_INI + 19}),\"\")", fmt="0.0", alinhar="center")
        ws.row_dimensions[r].height = 28
        r += 1
    ws.sheet_view.showGridLines = False


# --- SUS ---
def aba_sus_respostas(wb):
    ws = wb.create_sheet("SUS respostas")
    titulo(ws, "Respostas do SUS", "Uma linha por pessoa. Respostas de 1 (discordo totalmente) a 5 (concordo totalmente).")
    ws["A3"] = "A nota (0 a 100) só aparece com as 10 respostas preenchidas."
    ws["A3"].font = f(cor="595959", tamanho=9)
    colunas = [("ID", 7), ("Perfil", 12), ("Data", 12)] + [(f"P{i}", 6) for i in range(1, 11)] + [("Nota SUS", 10), ("Classificação", 13), ("Observações", 34)]
    cabecalho(ws, 4, colunas)
    for i, pergunta in enumerate(PERGUNTAS_SUS, start=1):
        ws.cell(row=4, column=3 + i).comment = Comment(f"P{i}. {pergunta}", "GalviTracks")
    escala = DataValidation(type="whole", operator="between", formula1="1", formula2="5",
                            error="Use 1, 2, 3, 4 ou 5.", showErrorMessage=True)
    perfis = DataValidation(type="list", formula1='"Operador,Gestor,Outro"', allow_blank=True)
    ws.add_data_validation(escala)
    ws.add_data_validation(perfis)
    for r in range(LINHA_INI, SUS_FIM + 1):
        celula(ws, f"A{r}", f"R{r - LINHA_INI + 1:02d}", alinhar="center")
        celula(ws, f"B{r}", entrada=True, alinhar="center")
        celula(ws, f"C{r}", entrada=True, fmt="dd/mm/yyyy", alinhar="center")
        for c in range(4, 14):
            celula(ws, f"{get_column_letter(c)}{r}", entrada=True, fmt="0", alinhar="center")
        soma = "+".join(f"({get_column_letter(c)}{r}-1)" if (c - 3) % 2 == 1 else f"(5-{get_column_letter(c)}{r})" for c in range(4, 14))
        celula(ws, f"N{r}", f'=IF(COUNT(D{r}:M{r})<10,"",({soma})*2.5)', fmt="0.0", alinhar="center", negrito=True)
        celula(ws, f"O{r}", f'=IF(N{r}="","",IF(N{r}>=85.5,"Excelente",IF(N{r}>=71.4,"Bom",IF(N{r}>=50.9,"OK",IF(N{r}>=35.7,"Ruim","Péssimo")))))', alinhar="center")
        celula(ws, f"P{r}", entrada=True)
    escala.add(f"D{LINHA_INI}:M{SUS_FIM}")
    perfis.add(f"B{LINHA_INI}:B{SUS_FIM}")
    ws.freeze_panes = f"D{LINHA_INI}"


def aba_sus_formulario(wb):
    ws = wb.create_sheet("SUS formulário")
    larguras = {"A": 5, "B": 50, "C": 10, "D": 8, "E": 8, "F": 8, "G": 10}
    for col, larg in larguras.items():
        ws.column_dimensions[col].width = larg
    ws["A1"] = "Questionário de usabilidade do GalviTracks (SUS)"
    ws["A1"].font = f(True, ROXO, 14)
    ws["A3"] = "Nome ou iniciais: ______________________   Função: ______________________   Data: ___/___/______"
    ws["A3"].font = f()
    ws["A5"] = ("Marque um X em cada linha: 1 = discordo totalmente, 5 = concordo totalmente. "
                "Responda pensando no uso do painel do GalviTracks nesta semana. Não há resposta certa ou errada.")
    ws["A5"].font = f(italico=True)
    ws["A5"].alignment = Alignment(wrap_text=True, vertical="top")
    ws.merge_cells("A5:G5")
    ws.row_dimensions[5].height = 30
    cabecalhos = ["Nº", "Afirmação", "1\nDiscordo totalmente", "2", "3", "4", "5\nConcordo totalmente"]
    for i, texto in enumerate(cabecalhos, start=1):
        c = ws.cell(row=7, column=i, value=texto)
        c.font = f(True, "FFFFFF")
        c.fill = CABECALHO
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BORDA
    ws.row_dimensions[7].height = 50
    for i, pergunta in enumerate(PERGUNTAS_SUS, start=1):
        r = 7 + i
        celula(ws, f"A{r}", i, alinhar="center", negrito=True)
        celula(ws, f"B{r}", pergunta)
        ws[f"B{r}"].font = f(tamanho=11)
        for col in "CDEFG":
            celula(ws, f"{col}{r}", "☐", alinhar="center")
            ws[f"{col}{r}"].font = Font(name=FONTE, size=14, color="737373")
        if i % 2 == 0:
            for col in "ABCDEFG":
                ws[f"{col}{r}"].fill = CINZA
        ws.row_dimensions[r].height = 34
    ws["A19"] = "Comentários (opcional):"
    ws["A19"].font = f(True)
    for r in range(20, 24):
        for col in "ABCDEFG":
            ws[f"{col}{r}"].border = Border(bottom=Side(style="thin", color="737373"))
        ws.row_dimensions[r].height = 26
    ws["A25"] = "Brooke (1996), tradução para o português. Obrigado pela participação!"
    ws["A25"].font = f(cor="737373", tamanho=8, italico=True)
    ws.page_setup.orientation = "portrait"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_area = "A1:G25"
    ws.sheet_view.showGridLines = False


def aba_motoboys(wb):
    ws = wb.create_sheet("Motoboys")
    titulo(ws, "Percepção dos motoboys (opcional)", "Escala de 1 (discordo totalmente) a 5 (concordo totalmente).")
    colunas = [("ID", 7), ("Motoboy", 16), ("Data", 12)] + [(f"M{i}", 10) for i in range(1, 5)] + [("Comentários", 50)]
    cabecalho(ws, 4, colunas)
    for i, pergunta in enumerate(PERGUNTAS_MOTOBOY, start=1):
        ws.cell(row=4, column=3 + i).comment = Comment(f"M{i}. {pergunta}", "GalviTracks")
    escala = DataValidation(type="whole", operator="between", formula1="1", formula2="5",
                            error="Use 1, 2, 3, 4 ou 5.", showErrorMessage=True)
    ws.add_data_validation(escala)
    for r in range(LINHA_INI, LINHA_INI + 20):
        celula(ws, f"A{r}", f"M{r - LINHA_INI + 1:02d}", alinhar="center")
        celula(ws, f"B{r}", entrada=True)
        celula(ws, f"C{r}", entrada=True, fmt="dd/mm/yyyy", alinhar="center")
        for col in "DEFG":
            celula(ws, f"{col}{r}", entrada=True, fmt="0", alinhar="center")
        celula(ws, f"H{r}", entrada=True)
    escala.add(f"D{LINHA_INI}:G{LINHA_INI + 19}")
    r = LINHA_INI + 21
    for i, pergunta in enumerate(PERGUNTAS_MOTOBOY, start=1):
        ws.cell(row=r, column=1, value=f"M{i}").font = f(True, ROXO)
        ws.cell(row=r, column=2, value=pergunta).font = f()
        r += 1
    ws.freeze_panes = f"D{LINHA_INI}"


def aba_incidentes(wb):
    ws = wb.create_sheet("Incidentes")
    titulo(ws, "Incidentes durante o piloto", "Tudo o que atrapalhou: sinal, internet, servidor, erro no painel, rota estranha.")
    cabecalho(ws, 4, [("Data", 12), ("Hora", 8), ("Tipo", 18), ("O que aconteceu", 46), ("Impacto no despacho", 26), ("Como foi resolvido", 34)])
    tipos = DataValidation(type="list", allow_blank=True,
                           formula1='"GPS sem sinal,Internet ou túnel,Servidor fechado,Erro no painel,Rota ou tempo errado,Celular do motoboy,Outro"')
    ws.add_data_validation(tipos)
    for r in range(LINHA_INI, LINHA_INI + 40):
        celula(ws, f"A{r}", entrada=True, fmt="dd/mm/yyyy", alinhar="center")
        celula(ws, f"B{r}", entrada=True, fmt="hh:mm", alinhar="center")
        for col in "CDEF":
            celula(ws, f"{col}{r}", entrada=True)
    tipos.add(f"C{LINHA_INI}:C{LINHA_INI + 39}")
    ws.freeze_panes = f"A{LINHA_INI}"


def gerar(saida=SAIDA):
    wb = Workbook()
    aba_leiame(wb)
    aba_medicao(wb, "Base (sem sistema)", "Cronometragem de base: sem o sistema",
                "Planejamento do despacho do jeito atual (telefone, WhatsApp, de cabeça).")
    aba_medicao(wb, "Piloto (com sistema)", "Cronometragem do piloto: com o GalviTracks",
                "Do início da montagem da rota no painel até o clique em \"Sair para entrega\".")
    aba_resumo(wb)
    aba_sus_respostas(wb)
    aba_sus_formulario(wb)
    aba_motoboys(wb)
    aba_incidentes(wb)
    for ws in wb.worksheets:
        ws.sheet_properties.tabColor = ROXO if ws.title in ("Leia-me", "Resumo") else "CEB7F0"
    saida = Path(saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    wb.save(saida)
    return saida


if __name__ == "__main__":
    print("planilha gerada:", gerar())
