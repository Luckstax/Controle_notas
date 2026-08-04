"""
O coracao do programa: validacao pre-escrita e a conciliacao FIFO
(decide de qual NF de saida cada devolucao veio).
"""

from modelos import SaldoNF

# cores de TEXTO usadas na coluna de prioridade/dias em aberto (Saldo por NF)
COR_TEXTO_VERDE = {"red": 0.0, "green": 0.5, "blue": 0.0}
COR_TEXTO_AMARELO = {"red": 0.72, "green": 0.53, "blue": 0.0}
COR_TEXTO_VERMELHO = {"red": 0.8, "green": 0.0, "blue": 0.0}

LIMITE_BAIXA_MEDIA = 30   # ate 30 dias em aberto = prioridade Baixa (verde)
LIMITE_MEDIA_ALTA = 89    # 31 a 89 dias = Media (amarelo); 90+ = Alta (vermelho)


def calcular_prioridade(dias_aberto, saldo_aberto):
    """Classifica a urgencia de uma NF em aberto com base em quantos
    dias ela esta fora. Quanto mais tempo fora, maior a prioridade de
    associar o proximo retorno a ela (e' a mesma logica que o FIFO ja
    usa para escolher a NF mais antiga primeiro - aqui so' tornamos
    isso visivel)."""
    if saldo_aberto <= 1e-9:
        return "Concluido", None
    if dias_aberto is None:
        return "Sem data", None
    if dias_aberto <= LIMITE_BAIXA_MEDIA:
        return "Baixa", COR_TEXTO_VERDE
    if dias_aberto <= LIMITE_MEDIA_ALTA:
        return "Media", COR_TEXTO_AMARELO
    return "Alta", COR_TEXTO_VERMELHO


# ----------------------------------------------------------------------
# Validacao pre-escrita: o Forms ajuda a evitar erro (produto invalido,
# etc.), mas nao pega tudo. Roda depois de ler Saida/Entrada e ANTES de
# escrever qualquer coisa na planilha, pra pegar problema de
# preenchimento cedo em vez de descobrir la na frente via SEM
# CORRESPONDENCIA. Sao avisos (nao interrompem a execucao).
# ----------------------------------------------------------------------
def validar_dados(saidas, entradas):
    avisos = []
    for s in saidas:
        if not s.fornecedor:
            avisos.append(f"[VALIDACAO] Saida linha {s.linha} (NF {s.nf or '?'}): fornecedor vazio.")
        if not s.nf:
            avisos.append(f"[VALIDACAO] Saida linha {s.linha}: numero da NF vazio.")
        if s.data is None:
            avisos.append(f"[VALIDACAO] Saida linha {s.linha} (NF {s.nf or '?'}): data de envio nao reconhecida/vazia.")
        for produto, qtd in s.produtos.items():
            if qtd < 0:
                avisos.append(f"[VALIDACAO] Saida linha {s.linha} (NF {s.nf or '?'}): "
                               f"quantidade negativa em '{produto}' ({qtd}).")
    for e in entradas:
        if not e.fornecedor:
            avisos.append(f"[VALIDACAO] Entrada linha {e.linha} (recebimento {e.nota_recebimento or '-'}): "
                           f"fornecedor vazio.")
        if not e.nota_recebimento:
            avisos.append(f"[VALIDACAO] Entrada linha {e.linha}: nota de recebimento vazia.")
        if e.data is None:
            avisos.append(f"[VALIDACAO] Entrada linha {e.linha} (recebimento {e.nota_recebimento or '-'}): "
                           f"data de recebimento nao reconhecida/vazia.")
        for produto, qtd in e.produtos.items():
            if qtd < 0:
                avisos.append(f"[VALIDACAO] Entrada linha {e.linha} (recebimento {e.nota_recebimento or '-'}): "
                               f"quantidade negativa em '{produto}' ({qtd}).")
    return avisos


# ----------------------------------------------------------------------
# Conciliacao / alocacao FIFO
#
# Por produto, dentro de cada linha de Entrada:
#   1. Tenta usar as "notas mencionadas" (ate 5, na ordem preenchida no
#      formulario de retorno), uma de cada vez. Se a NF existir e tiver
#      saldo em aberto daquele produto, aloca ali; se sobrar, tenta a
#      proxima nota mencionada.
#   2. Se ainda sobrar (nota mencionada errada, sem saldo suficiente, ou
#      nao encontrada), o restante "escorre" em FIFO pelas NFs mais
#      antigas em aberto do MESMO FORNECEDOR e MESMO PRODUTO.
#   3. Se ainda sobrar, fica marcado como "SEM CORRESPONDENCIA" para
#      revisao manual - isso nao e' necessariamente um erro (pode ser
#      retorno de nota de saida antiga, de antes do sistema existir).
# ----------------------------------------------------------------------
def conciliar(saidas, entradas):
    saldo_map = {}
    for s in saidas:
        for produto, qtd in s.produtos.items():
            saldo_map[(s.nf, produto)] = SaldoNF(
                nf=s.nf, serie=s.serie, data=s.data,
                fornecedor=s.fornecedor, produto=produto, enviado=qtd,
            )

    alocacoes = []
    avisos = []

    entradas_ordenadas = sorted(entradas, key=lambda e: (e.data is None, e.data))

    for e in entradas_ordenadas:
        for produto, qtd_total in e.produtos.items():
            restante = qtd_total

            if not e.notas_mencionadas:
                avisos.append(
                    f"Entrada linha {e.linha} (recebimento {e.nota_recebimento or '-'}): "
                    f"nenhuma nota mencionada informada para o produto '{produto}' "
                    f"(tentando alocar via FIFO)."
                )

            notas_nao_encontradas = []
            for posicao, nota in enumerate(e.notas_mencionadas, start=1):
                if restante <= 1e-9:
                    break
                chave = (nota, produto)
                origem_mencionada = saldo_map.get(chave)
                if origem_mencionada is None:
                    notas_nao_encontradas.append(nota)
                    continue
                if origem_mencionada.fornecedor != e.fornecedor:
                    avisos.append(
                        f"Entrada linha {e.linha}: fornecedor '{e.fornecedor}' diverge do "
                        f"fornecedor '{origem_mencionada.fornecedor}' da nota mencionada "
                        f"{posicao} ('{nota}'). Confira os dados."
                    )
                if (origem_mencionada.data and e.data
                        and e.data < origem_mencionada.data):
                    avisos.append(
                        f"[VALIDACAO] Entrada linha {e.linha}: data de entrada "
                        f"({e.data:%d/%m/%Y}) e anterior a data de saida da nota "
                        f"mencionada {posicao} '{nota}' ({origem_mencionada.data:%d/%m/%Y}). "
                        f"Confira as datas."
                    )
                if origem_mencionada.disponivel > 1e-9:
                    usar = min(restante, origem_mencionada.disponivel)
                    origem_mencionada.alocado += usar
                    restante = round(restante - usar, 6)
                    alocacoes.append(dict(
                        entrada_linha=e.linha, nota_recebimento=e.nota_recebimento,
                        data_entrada=e.data, fornecedor=e.fornecedor, produto=produto,
                        nf_saida=origem_mencionada.nf, quantidade=usar,
                        origem=f"nota mencionada {posicao}",
                    ))

            if notas_nao_encontradas:
                avisos.append(
                    f"Entrada linha {e.linha} (recebimento {e.nota_recebimento or '-'}): "
                    f"nota(s) mencionada(s) {', '.join(repr(n) for n in notas_nao_encontradas)} "
                    f"nao encontrada(s) nas saidas para o produto '{produto}'."
                )

            if restante > 1e-9:
                candidatos = sorted(
                    [v for (nf, p), v in saldo_map.items()
                     if p == produto and v.fornecedor == e.fornecedor and v.disponivel > 1e-9],
                    key=lambda v: (v.data is None, v.data),
                )
                for cand in candidatos:
                    if restante <= 1e-9:
                        break
                    usar = min(restante, cand.disponivel)
                    cand.alocado += usar
                    restante = round(restante - usar, 6)
                    alocacoes.append(dict(
                        entrada_linha=e.linha, nota_recebimento=e.nota_recebimento,
                        data_entrada=e.data, fornecedor=e.fornecedor, produto=produto,
                        nf_saida=cand.nf, quantidade=usar, origem="fifo (sobra)",
                    ))

            if restante > 1e-9:
                alocacoes.append(dict(
                    entrada_linha=e.linha, nota_recebimento=e.nota_recebimento,
                    data_entrada=e.data, fornecedor=e.fornecedor, produto=produto,
                    nf_saida=None, quantidade=restante, origem="SEM CORRESPONDENCIA",
                ))
                avisos.append(
                    f"Entrada linha {e.linha}: sobraram {restante} unidades do produto "
                    f"'{produto}' sem NF de saida em aberto do fornecedor '{e.fornecedor}'."
                )

    return saldo_map, alocacoes, avisos
