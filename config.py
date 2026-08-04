"""
Leitura automatica de credenciais/planilha do arquivo credenciais.env
(assim ninguem precisa digitar --credenciais/--planilha toda vez).
"""

import os


def caminho_env_padrao():
    candidatos = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "credenciais.env"),
        r"C:\Users\maua\Desktop\programação\notas\credenciais.env",
    ]
    for c in candidatos:
        if os.path.exists(c):
            return c
    return candidatos[0]


def carregar_env(caminho):
    """Le um arquivo tipo 'chave = "valor"' (uma por linha) e devolve um
    dict com chaves em minusculo. Tolerante a aspas simples/duplas que
    faltam no fim da linha, espacos e quebras de linha do Windows."""
    valores = {}
    if not caminho or not os.path.exists(caminho):
        return valores
    with open(caminho, "r", encoding="utf-8-sig") as f:
        for linha in f:
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            chave, _, valor = linha.partition("=")
            chave = chave.strip().lower()
            valor = valor.strip().strip('"').strip("'")
            valores[chave] = valor
    return valores
