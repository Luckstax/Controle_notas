"""
Leitura e parsing das abas Saida e Entrada: converte as linhas da
planilha em NotaSaida/NotaEntrada, e resolve apelidos de fornecedor.
"""

from datetime import datetime

from modelos import NotaSaida, NotaEntrada
from planilha_io import (
    normalizar, mapear_cabecalhos, achar_coluna,
    achar_colunas_notas_mencionadas, achar_todas_colunas, valor_mesclado,
)

# ----------------------------------------------------------------------
# Apelidos de fornecedor: como o campo "Fornecedor" tem a opcao "Outro"
# (texto livre) tanto na Saida quanto na Entrada, a mesma empresa pode
# acabar escrita de jeitos diferentes (ex: "Sam Correia" vs "Sam Correia
# Ltda"). O programa exige texto identico pra casar saida com entrada,
# entao qualquer variacao quebra a conciliacao (cai em SEM
# CORRESPONDENCIA mesmo tendo saldo disponivel).
#
# Use este dicionario pra "traduzir" variacoes conhecidas pro nome
# padrao. A chave e o texto como foi digitado (normalizado: minusculo,
# sem espaco extra) e o valor e o nome padrao que deve ser usado daqui
# pra frente. Va adicionando aqui conforme forem aparecendo variacoes
# novas na planilha.
#
# Exemplo:
#   FORNECEDOR_ALIASES = {
#       "sam correia ltda": "sam correia",
#       "high color com. e ind.": "high color",
#   }
FORNECEDOR_ALIASES = {
    # "texto digitado (minusculo)": "nome padrao",
}


def normalizar_fornecedor(texto):
    valor = normalizar(texto)
    return FORNECEDOR_ALIASES.get(valor, valor)


def identificar_colunas_produto(ws):
    pares = []
    for col in range(1, ws.max_column):
        h_atual = normalizar(ws.cell(row=1, column=col).value)
        h_prox = normalizar(ws.cell(row=1, column=col + 1).value)
        if h_atual and h_prox.startswith("quant"):
            codigo = ws.cell(row=1, column=col).value
            pares.append((codigo, col, col + 1))
    return pares


def para_data(v):
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v
    texto = str(v).strip()
    formatos = ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d")
    for fmt in formatos:
        try:
            return datetime.strptime(texto, fmt)
        except ValueError:
            continue
    return None


def para_float(v):
    if v is None or v == "":
        return 0.0
    texto = str(v).strip().replace(".", "").replace(",", ".") if isinstance(v, str) and "," in str(v) else v
    try:
        return float(texto)
    except (TypeError, ValueError):
        return 0.0


def ler_saidas(ws):
    headers = mapear_cabecalhos(ws)
    col_data = achar_coluna(headers, ("data",))
    col_nf = achar_coluna(headers, ("numero", "nota", "fiscal"))
    col_serie = achar_coluna(headers, ("serie",))
    col_tipo = achar_coluna(headers, ("tipo",))
    cols_fornecedor = achar_todas_colunas(ws, ("fornecedor",))
    produtos_cols = identificar_colunas_produto(ws)

    faltando = [n for n, c in [("data", col_data), ("numero da nota fiscal", col_nf)] if c is None]
    if not cols_fornecedor:
        faltando.append("fornecedor")
    if faltando:
        raise ValueError(f"Aba Saida: nao encontrei as colunas: {', '.join(faltando)}")

    saidas = []
    for row in range(2, ws.max_row + 1):
        nf = ws.cell(row=row, column=col_nf).value
        if nf is None or str(nf).strip() == "":
            continue
        produtos = {}
        for codigo, col_cod, col_qtd in produtos_cols:
            qtd = para_float(ws.cell(row=row, column=col_qtd).value)
            if qtd > 0:
                produtos[normalizar(codigo)] = qtd
        saidas.append(NotaSaida(
            linha=row,
            data=para_data(ws.cell(row=row, column=col_data).value),
            nf=normalizar(nf),
            serie=str(ws.cell(row=row, column=col_serie).value or "").strip(),
            tipo=str(ws.cell(row=row, column=col_tipo).value or "").strip(),
            fornecedor=normalizar_fornecedor(valor_mesclado(ws, row, cols_fornecedor, "Fornecedor")),
            produtos=produtos,
        ))
    return saidas


def ler_entradas(ws):
    headers = mapear_cabecalhos(ws)
    col_data = achar_coluna(headers, ("data", "recebimento"))
    col_nota_receb = achar_coluna(headers, ("nota", "recebimento"), nao_contem=("data",))
    col_serie_receb = achar_coluna(headers, ("serie", "recebimento"))
    cols_mencionadas = achar_colunas_notas_mencionadas(ws)
    col_tipo = achar_coluna(headers, ("tipo",))
    cols_fornecedor = achar_todas_colunas(ws, ("fornecedor",))
    produtos_cols = identificar_colunas_produto(ws)

    faltando = [n for n, c in [("data de recebimento", col_data)] if c is None]
    if not cols_fornecedor:
        faltando.append("fornecedor")
    if not cols_mencionadas:
        faltando.append("nota mencionada")
    if faltando:
        raise ValueError(f"Aba Entrada: nao encontrei as colunas: {', '.join(faltando)}")

    entradas = []
    for row in range(2, ws.max_row + 1):
        notas_mencionadas = []
        vistas = set()
        for col in cols_mencionadas:
            valor = normalizar(ws.cell(row=row, column=col).value)
            if valor and valor not in vistas:
                vistas.add(valor)
                notas_mencionadas.append(valor)
        tem_produto = any(
            para_float(ws.cell(row=row, column=col_qtd).value) > 0
            for _, _, col_qtd in produtos_cols
        )
        if not tem_produto:
            continue
        produtos = {}
        for codigo, col_cod, col_qtd in produtos_cols:
            qtd = para_float(ws.cell(row=row, column=col_qtd).value)
            if qtd > 0:
                produtos[normalizar(codigo)] = qtd
        entradas.append(NotaEntrada(
            linha=row,
            data=para_data(ws.cell(row=row, column=col_data).value),
            nota_recebimento=str(ws.cell(row=row, column=col_nota_receb).value or "").strip() if col_nota_receb else "",
            serie_recebimento=str(ws.cell(row=row, column=col_serie_receb).value or "").strip() if col_serie_receb else "",
            notas_mencionadas=tuple(notas_mencionadas),
            tipo=str(ws.cell(row=row, column=col_tipo).value or "").strip(),
            fornecedor=normalizar_fornecedor(valor_mesclado(ws, row, cols_fornecedor, "Fornecedor")),
            produtos=produtos,
        ))
    return entradas
