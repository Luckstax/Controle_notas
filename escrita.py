"""
Escrita do resultado da conciliacao de volta na planilha: abas
Alocacoes, Saldo por NF, Avisos, Controle e Retorno por NF e Fornecedor.
"""

from datetime import datetime

import gspread

from planilha_io import com_retry, obter_ou_criar_aba, normalizar
from conciliacao import calcular_prioridade

COR_VERDE = {"red": 0.78, "green": 0.94, "blue": 0.81}
COR_AMARELO = {"red": 1.0, "green": 0.92, "blue": 0.61}
COR_VERMELHO = {"red": 1.0, "green": 0.78, "blue": 0.81}
COR_CINZA = {"red": 0.85, "green": 0.85, "blue": 0.85}
COR_BRANCO = {"red": 1.0, "green": 1.0, "blue": 1.0}
COR_TEXTO_PADRAO = {"red": 0.0, "green": 0.0, "blue": 0.0}  # preto, cor normal de texto


def _fmt_data(d):
    return d.strftime("%d/%m/%Y") if isinstance(d, datetime) else ""


def _fmt_qtd(q):
    """Formata quantidade de um jeito estavel pra comparar com o texto
    que o Google Sheets devolve na leitura (evita 'falso novo' so por
    causa de 10.0 vs 10)."""
    q = round(float(q), 6)
    return str(int(q)) if q == int(q) else str(q)


@com_retry
def ler_avisos_anteriores(sh):
    """Le os avisos que ja estavam na aba Avisos ANTES desta execucao
    (antes dela ser recriada), pra depois sabermos quais avisos sao
    novos. Devolve um conjunto de textos."""
    try:
        ws = sh.worksheet("Avisos")
    except gspread.WorksheetNotFound:
        return set()
    valores = ws.get_all_values()
    return {linha[0] for linha in valores[1:] if linha and linha[0]}


@com_retry
def ler_alocacoes_anteriores(sh):
    """Le as alocacoes que ja estavam na aba Alocacoes ANTES desta
    execucao (antes dela ser recriada), pra depois sabermos quantas
    sao novas. Devolve um conjunto de 'assinaturas' (recebimento,
    produto, NF final, quantidade, origem)."""
    try:
        ws = sh.worksheet("Alocacoes")
    except gspread.WorksheetNotFound:
        return set()
    valores = ws.get_all_values()
    if len(valores) < 2:
        return set()
    header = valores[0]
    try:
        i_receb = header.index("Nota Recebimento")
        i_prod = header.index("Produto")
        i_final = header.index("NF Saida (final)")
        i_qtd = header.index("Quantidade")
        i_origem = header.index("Origem")
    except ValueError:
        return set()

    assinaturas = set()
    for linha in valores[1:]:
        if len(linha) <= max(i_receb, i_prod, i_final, i_qtd, i_origem):
            continue
        assinaturas.add((
            linha[i_receb], normalizar(linha[i_prod]), normalizar(linha[i_final]),
            linha[i_qtd], linha[i_origem],
        ))
    return assinaturas


def contar_alocacoes_novas(alocacoes, assinaturas_anteriores):
    """Compara as alocacoes desta execucao (ja com 'nf_saida_final'
    preenchido por escrever_alocacoes) com as assinaturas de antes, e
    devolve quantas sao genuinamente novas."""
    novas = 0
    for a in alocacoes:
        nf_final = a.get("nf_saida_final", a["nf_saida"] or "")
        assinatura = (
            a["nota_recebimento"], normalizar(a["produto"]), normalizar(nf_final),
            _fmt_qtd(a["quantidade"]), a["origem"],
        )
        if assinatura not in assinaturas_anteriores:
            novas += 1
    return novas


def contar_avisos_novos(avisos, avisos_anteriores):
    return sum(1 for a in avisos if a not in avisos_anteriores)


@com_retry
def ler_overrides_anteriores(sh):
    """Le a aba Alocacoes ANTES dela ser recriada, e devolve um dict
    {(nota_recebimento, produto, nf_sugerida): nf_final_digitada}
    apenas para as linhas onde alguem editou manualmente a coluna
    'NF Saida (final)' (ou seja, ela ficou diferente da sugestao).
    Isso permite reaplicar os ajustes manuais depois de recalcular."""
    try:
        ws = sh.worksheet("Alocacoes")
    except gspread.WorksheetNotFound:
        return {}

    valores = ws.get_all_values()
    if len(valores) < 2:
        return {}

    header = valores[0]
    try:
        i_receb = header.index("Nota Recebimento")
        i_prod = header.index("Produto")
        i_sug = header.index("NF Saida (sugerida)")
        i_final = header.index("NF Saida (final)")
    except ValueError:
        return {}  # aba com formato antigo/inesperado, ignora com seguranca

    overrides = {}
    for linha in valores[1:]:
        if len(linha) <= max(i_receb, i_prod, i_sug, i_final):
            continue
        sugerida = normalizar(linha[i_sug])
        final = normalizar(linha[i_final])
        if final and final != sugerida:
            chave = (linha[i_receb], normalizar(linha[i_prod]), sugerida)
            overrides[chave] = linha[i_final]
    return overrides


@com_retry
def escrever_alocacoes(sh, alocacoes, overrides, avisos):
    ws = obter_ou_criar_aba(sh, "Alocacoes")
    cabecalho = ["Linha Entrada", "Nota Recebimento", "Data Entrada", "Fornecedor",
                 "Produto", "NF Saida (sugerida)", "NF Saida (final)", "Quantidade",
                 "Origem", "Observacao"]
    linhas = [cabecalho]
    cores_linha = [None]
    for a in alocacoes:
        sugerida = a["nf_saida"] or ""
        chave = (a["nota_recebimento"], normalizar(a["produto"]), normalizar(sugerida))
        final = overrides.get(chave, sugerida)
        obs = "ajuste manual preservado" if chave in overrides else ""
        a["nf_saida_final"] = final  # usado depois no calculo de saldo

        linhas.append([
            a["entrada_linha"], a["nota_recebimento"], _fmt_data(a["data_entrada"]),
            a["fornecedor"], a["produto"], sugerida, final,
            a["quantidade"], a["origem"], obs,
        ])
        if a["origem"] == "SEM CORRESPONDENCIA":
            cores_linha.append(COR_VERMELHO)
        elif chave in overrides:
            cores_linha.append(None)
        elif a["origem"].startswith("fifo"):
            cores_linha.append(COR_AMARELO)
        else:
            cores_linha.append(None)

    # overrides que nao encontraram par na nova rodada (a sugestao mudou)
    chaves_usadas = {
        (a["nota_recebimento"], normalizar(a["produto"]), normalizar(a["nf_saida"] or ""))
        for a in alocacoes
    }
    for chave_antiga in overrides:
        if chave_antiga not in chaves_usadas:
            avisos.append(
                f"Ajuste manual anterior nao pode ser reaplicado automaticamente: "
                f"recebimento '{chave_antiga[0]}', produto '{chave_antiga[1]}' - "
                f"a sugestao do FIFO mudou desde a ultima execucao. Revise a aba Alocacoes."
            )

    ws.update(values=linhas, range_name="A1")
    ws.format("A1:J1", {"textFormat": {"bold": True}, "backgroundColor": COR_CINZA})
    ultima_linha = len(linhas)
    if ultima_linha > 1:
        # reseta o fundo de TODAS as linhas de dado antes de recolorir.
        # O clear() do Sheets so apaga valor, nao cor - sem esse reset,
        # uma linha "sem problema" hoje podia ficar com o vermelho/
        # amarelo de uma execucao anterior, se essa mesma posicao de
        # linha antes fosse SEM CORRESPONDENCIA ou fifo (sobra).
        ws.format(f"A2:J{ultima_linha}", {"backgroundColor": COR_BRANCO})
    for i, cor in enumerate(cores_linha):
        if cor is None or i == 0:
            continue
        linha_planilha = i + 1
        ws.format(f"A{linha_planilha}:J{linha_planilha}", {"backgroundColor": cor})
    ws.freeze(rows=1)
    return ws


@com_retry
def escrever_saldo(sh, saldo_map, alocacoes):
    ws = obter_ou_criar_aba(sh, "Saldo por NF")
    cabecalho = ["NF Saida", "Serie", "Data Envio", "Fornecedor", "Produto",
                 "Qtd Enviada", "Qtd Retornada", "Saldo em Aberto", "Dias em Aberto",
                 "Prioridade", "% Retornado"]

    hoje = datetime.now()
    retornado_por_chave = {}
    for a in alocacoes:
        nf_efetiva = normalizar(a.get("nf_saida_final", a["nf_saida"]))
        if nf_efetiva:
            chave = (nf_efetiva, a["produto"])
            retornado_por_chave[chave] = retornado_por_chave.get(chave, 0) + a["quantidade"]

    calculadas = []
    for s in saldo_map.values():
        retornado = retornado_por_chave.get((s.nf, s.produto), 0.0)
        saldo_aberto = round(s.enviado - retornado, 6)
        dias_aberto = (hoje - s.data).days if isinstance(s.data, datetime) else None
        pct = round(100 * retornado / s.enviado, 1) if s.enviado else 0
        prioridade, cor_texto = calcular_prioridade(dias_aberto, saldo_aberto)
        calculadas.append(dict(s=s, retornado=retornado, saldo_aberto=saldo_aberto,
                                dias_aberto=dias_aberto, prioridade=prioridade,
                                cor_texto=cor_texto, pct=pct))

    # prioridade visual: pendentes primeiro, com mais dias em aberto no topo
    # (a NF parada ha mais tempo e' a sugestao prioritaria pra associar o
    # proximo retorno) - concluidas ficam no final da lista.
    def chave_ordenacao(item):
        pendente = item["saldo_aberto"] > 1e-9
        return (
            0 if pendente else 1,
            -(item["dias_aberto"] or 0) if pendente else 0,
            item["s"].fornecedor, item["s"].nf, item["s"].produto,
        )
    calculadas.sort(key=chave_ordenacao)

    linhas = [cabecalho]
    cores_texto = [None]
    for item in calculadas:
        s = item["s"]
        linhas.append([
            s.nf, s.serie, _fmt_data(s.data), s.fornecedor, s.produto,
            s.enviado, item["retornado"], item["saldo_aberto"],
            item["dias_aberto"] if item["dias_aberto"] is not None else "",
            item["prioridade"], item["pct"],
        ])
        cores_texto.append(item["cor_texto"])

    ws.update(values=linhas, range_name="A1")
    ws.format("A1:K1", {"textFormat": {"bold": True}, "backgroundColor": COR_CINZA})
    ultima_linha = len(linhas)
    if ultima_linha > 1:
        # reseta a formatacao da coluna de prioridade ANTES de recolorir.
        # O clear() do Sheets so apaga valor, nao cor/formatacao - sem
        # esse reset, uma linha que hoje e' "Concluido" (sem cor) podia
        # ficar com a cor de uma execucao anterior, se essa mesma
        # posicao de linha antes tivesse "Alta"/"Media"/"Baixa".
        ws.format(f"I2:J{ultima_linha}", {"textFormat": {"foregroundColor": COR_TEXTO_PADRAO, "bold": False}})
    for i, cor in enumerate(cores_texto):
        if i == 0 or cor is None:
            continue
        linha_planilha = i + 1
        ws.format(f"I{linha_planilha}:J{linha_planilha}", {"textFormat": {"foregroundColor": cor, "bold": True}})
    ws.freeze(rows=1)
    return ws


@com_retry
def escrever_avisos(sh, avisos):
    ws = obter_ou_criar_aba(sh, "Avisos")
    linhas = [["Avisos de conciliacao (revisar manualmente)"]]
    linhas += [[a] for a in avisos]
    ws.update(values=linhas, range_name="A1")
    ws.format("A1", {"textFormat": {"bold": True}})
    ws.freeze(rows=1)
    return ws


@com_retry
def preencher_controle(sh, saidas, entradas):
    """Preenche a aba Controle (coluna B = total Saida, coluna C =
    total Entrada) casando pelo nome do produto na coluna A. Celulas
    que ja contiverem uma FORMULA propria (ex: voce colocou um
    SOMASE manualmente) sao respeitadas e NAO sao sobrescritas -
    o script so preenche onde a celula esta vazia ou com valor fixo."""
    try:
        ws = sh.worksheet("Controle")
    except gspread.WorksheetNotFound:
        return

    total_saida, total_entrada = {}, {}
    for s in saidas:
        for produto, qtd in s.produtos.items():
            total_saida[produto] = total_saida.get(produto, 0) + qtd
    for e in entradas:
        for produto, qtd in e.produtos.items():
            total_entrada[produto] = total_entrada.get(produto, 0) + qtd

    rotulos = ws.col_values(1)
    max_row = len(rotulos)
    if max_row < 2:
        return

    # le as FORMULAS (nao os valores calculados) de B2:C(max_row) para
    # saber quais celulas ja tem logica propria do usuario
    formulas_bc = ws.get(f"B2:C{max_row}", value_render_option="FORMULA")

    atualizacoes = []
    puladas = []
    for i, rotulo in enumerate(rotulos):
        row = i + 1
        if row == 1 or not rotulo:
            continue
        idx = row - 2
        linha_formula = formulas_bc[idx] if idx < len(formulas_bc) else []
        celula_b = linha_formula[0] if len(linha_formula) > 0 else ""
        celula_c = linha_formula[1] if len(linha_formula) > 1 else ""
        if str(celula_b).startswith("=") or str(celula_c).startswith("="):
            puladas.append(rotulo)
            continue

        codigo = normalizar(rotulo)
        if codigo.startswith("quantidade"):
            codigo = codigo[len("quantidade"):].strip()
        atualizacoes.append({
            "range": f"B{row}:C{row}",
            "values": [[total_saida.get(codigo, 0), total_entrada.get(codigo, 0)]],
        })

    if atualizacoes:
        ws.batch_update(atualizacoes)
    if puladas:
        print(f"Controle: {len(puladas)} linha(s) com formula propria preservada(s) sem alteracao.")


# ----------------------------------------------------------------------
# Aba "Retorno por NF e Fornecedor": uma linha por nota de saida, com o
# fornecedor e, para cada item, quanto ja voltou. Usa o resultado ja
# calculado das Alocacoes (nao soma direto das entradas), porque uma
# entrada pode mencionar ate 5 notas e a conciliacao ja resolveu quanto
# de cada item foi de fato atribuido a cada NF de saida.
# ----------------------------------------------------------------------
@com_retry
def escrever_retorno_por_nf(sh, saidas, alocacoes):
    produtos = sorted({p for s in saidas for p in s.produtos}
                       | {a["produto"] for a in alocacoes})
    if not produtos:
        return

    retorno_por_nf = {}
    for a in alocacoes:
        nf = a.get("nf_saida")
        if not nf:
            continue  # SEM CORRESPONDENCIA - nao pertence a nenhuma NF de saida
        chave_nf = normalizar(nf)
        totais = retorno_por_nf.setdefault(chave_nf, {})
        totais[a["produto"]] = totais.get(a["produto"], 0) + a["quantidade"]

    cabecalho = ["Fornecedor", "NF", "Serie", "Data"] + produtos
    linhas = [cabecalho]
    for s in sorted(saidas, key=lambda s: (normalizar(s.fornecedor), s.nf)):
        retorno = retorno_por_nf.get(normalizar(s.nf), {})
        linha = [s.fornecedor, s.nf, s.serie, _fmt_data(s.data)]
        linha += [round(retorno.get(p, 0), 6) for p in produtos]
        linhas.append(linha)

    ws = obter_ou_criar_aba(sh, "Retorno por NF e Fornecedor")
    ws.clear()
    ws.update(values=linhas, range_name="A1")
    ultima_col = gspread.utils.rowcol_to_a1(1, len(cabecalho)).rstrip("1")
    ws.format(f"A1:{ultima_col}1", {"textFormat": {"bold": True}, "backgroundColor": COR_CINZA})
    ws.freeze(rows=1)
    print("Aba 'Retorno por NF e Fornecedor' atualizada.")
