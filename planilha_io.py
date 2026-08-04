"""
Utilidades de baixo nivel pra falar com o Google Sheets: conexao,
leitura de abas, localizacao de colunas pelo cabecalho, e o retry
automatico pra erros de limite de taxa/servidor temporario.
"""

import time

import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def normalizar(texto):
    if texto is None:
        return ""
    return " ".join(str(texto).strip().lower().split())


# ----------------------------------------------------------------------
# Retry com espera crescente: o Google Sheets tem limite de quantas
# chamadas por minuto voce pode fazer. Se o script tomar um erro de
# "limite de taxa" (429) ou um erro temporario do servidor (500/503),
# em vez de quebrar na hora, ele espera um pouco e tenta de novo (2s,
# depois 4s, 8s...) ate 5 tentativas antes de desistir de verdade.
# ----------------------------------------------------------------------
def com_retry(func):
    def wrapper(*args, **kwargs):
        max_tentativas = 5
        espera = 2
        for tentativa in range(1, max_tentativas + 1):
            try:
                return func(*args, **kwargs)
            except gspread.exceptions.APIError as erro:
                status = None
                try:
                    status = erro.response.status_code
                except Exception:
                    pass
                if status in (429, 500, 503) and tentativa < max_tentativas:
                    print(f"  (Google Sheets ocupado - tentativa {tentativa}/{max_tentativas}, "
                          f"aguardando {espera}s antes de tentar de novo...)")
                    time.sleep(espera)
                    espera *= 2
                    continue
                raise
    return wrapper


# ----------------------------------------------------------------------
# Adaptador: transforma a matriz de valores do Google Sheets numa
# interface parecida com Worksheet do openpyxl (mesmo cell().value),
# assim a leitura (em leitura.py) fica identica independente da fonte.
# ----------------------------------------------------------------------
class _Celula:
    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value


class TabelaSimples:
    def __init__(self, linhas):
        self.linhas = linhas
        self.max_row = len(linhas)
        self.max_column = max((len(l) for l in linhas), default=0)

    def cell(self, row, column):
        r, c = row - 1, column - 1
        if 0 <= r < len(self.linhas):
            linha = self.linhas[r]
            if 0 <= c < len(linha) and linha[c] != "":
                return _Celula(linha[c])
        return _Celula(None)


# ----------------------------------------------------------------------
# Conexao com o Google Sheets
# ----------------------------------------------------------------------
@com_retry
def conectar(caminho_credenciais, planilha_url_ou_id):
    creds = Credentials.from_service_account_file(caminho_credenciais, scopes=SCOPES)
    gc = gspread.authorize(creds)
    if planilha_url_ou_id.startswith("http"):
        return gc.open_by_url(planilha_url_ou_id)
    return gc.open_by_key(planilha_url_ou_id)


@com_retry
def obter_aba(sh, nome):
    try:
        return sh.worksheet(nome)
    except gspread.WorksheetNotFound:
        raise SystemExit(f"A planilha nao tem uma aba chamada '{nome}'.")


@com_retry
def ler_matriz(ws_gspread):
    """Le todos os valores como texto (mesmo comportamento do Google
    Sheets exibido em tela) e devolve envolvido no adaptador TabelaSimples."""
    valores = ws_gspread.get_all_values()
    return TabelaSimples(valores)


@com_retry
def obter_ou_criar_aba(sh, nome, linhas=1000, colunas=26):
    try:
        ws = sh.worksheet(nome)
        ws.clear()
        return ws
    except gspread.WorksheetNotFound:
        return sh.add_worksheet(title=nome, rows=linhas, cols=colunas)


# ----------------------------------------------------------------------
# Localizacao de colunas pelo texto do cabecalho (linha 1). Assim a
# posicao (letra) das colunas pode mudar na planilha sem quebrar o
# script - ele acha pelo nome, nao pela letra.
# ----------------------------------------------------------------------
def mapear_cabecalhos(ws):
    headers = {}
    for col in range(1, ws.max_column + 1):
        val = ws.cell(row=1, column=col).value
        if val is not None:
            headers[normalizar(val)] = col
    return headers


def achar_coluna(headers, contem_todos=(), nao_contem=(), qualquer_de=None):
    for h, col in headers.items():
        if not all(t in h for t in contem_todos):
            continue
        if any(t in h for t in nao_contem):
            continue
        if qualquer_de is not None and not any(t in h for t in qualquer_de):
            continue
        return col
    return None


def achar_colunas_notas_mencionadas(ws):
    """Retorna, em ordem de coluna, todas as colunas 'nota mencionada N'
    (aceita a variacao 'mensionada'). Ignora colunas de gatilho do Forms
    tipo 'Outra nota mencionada?' e qualquer coluna de 'serie mencionada'.
    Varre a planilha direto (em vez de usar o dict de headers) porque o
    Forms repete o cabecalho 'Outra nota mencionada?' varias vezes, e um
    dict perderia as colunas repetidas."""
    cols = []
    for col in range(1, ws.max_column + 1):
        h = normalizar(ws.cell(row=1, column=col).value)
        if not h:
            continue
        if "outra" in h or "serie" in h:
            continue
        if "mencionada" in h or "mensionada" in h:
            cols.append(col)
    return cols


def achar_todas_colunas(ws, contem_todos=(), nao_contem=()):
    """Como achar_coluna, mas devolve TODAS as colunas que combinam (nao
    so a primeira). Usado quando pode haver cabecalho duplicado na
    planilha (ex: duas colunas 'Fornecedor' por causa de uma pergunta
    do Forms que foi removida e recriada)."""
    cols = []
    for col in range(1, ws.max_column + 1):
        h = normalizar(ws.cell(row=1, column=col).value)
        if not h:
            continue
        if not all(t in h for t in contem_todos):
            continue
        if any(t in h for t in nao_contem):
            continue
        cols.append(col)
    return cols


def valor_mesclado(ws, row, colunas, rotulo=""):
    """Le o valor de uma linha em varias colunas candidatas (cabecalhos
    duplicados, ex: duas colunas 'Fornecedor') e devolve o primeiro
    valor nao vazio, da esquerda pra direita. Se mais de uma coluna
    tiver valor E forem diferentes entre si, imprime um aviso no
    console (nao trava a execucao) pra facilitar encontrar o conflito."""
    escolhido = None
    vistos = []
    for col in colunas:
        v = ws.cell(row=row, column=col).value
        v_texto = str(v).strip() if v not in (None, "") else ""
        if v_texto:
            vistos.append(v_texto)
            if escolhido is None:
                escolhido = v_texto
    if len(set(vistos)) > 1:
        print(f"  aviso: linha {row}{' (' + rotulo + ')' if rotulo else ''}: colunas "
              f"duplicadas de '{rotulo or 'campo'}' com valores diferentes "
              f"({', '.join(repr(v) for v in vistos)}) - usando '{escolhido}'.")
    return escolhido or ""
