"""
O coracao do programa: validacao pre-escrita e a conciliacao por notas
mencionadas (decide de qual NF de saida cada devolucao veio).
"""

from datetime import datetime

from modelos import SaldoNF
from planilha_io import normalizar

LIMITE_BAIXA_MEDIA = 30   # ate 30 dias em aberto = prioridade Baixa (verde)
LIMITE_MEDIA_ALTA = 89    # 31 a 89 dias = Media (amarelo); 90+ = Alta (vermelho)

# As cores (verde/amarelo/vermelho) NAO sao mais aplicadas por aqui -
# essa funcao so' devolve o texto da prioridade. A cor correspondente e'
# configurada direto no Google Sheets via formatacao condicional (ver
# README), entao nao faz sentido manter constantes de cor sem uso aqui.


def calcular_prioridade(dias_aberto, saldo_aberto):
    """Classifica a urgencia de uma NF em aberto com base em quantos
    dias ela esta fora. Quanto mais tempo fora, maior a prioridade de
    associar um retorno a ela (so' torna visivel a idade da NF)."""
    if saldo_aberto <= 1e-9:
        return "Concluido"
    if dias_aberto is None:
        return "Sem data"
    if dias_aberto <= LIMITE_BAIXA_MEDIA:
        return "Baixa"
    if dias_aberto <= LIMITE_MEDIA_ALTA:
        return "Media"
    return "Alta"


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
# Conciliacao / alocacao - SEM FIFO.
#
# Regra unica: cada entrada so' consome saldo das notas que ELA MESMA
# mencionou, na ordem em que foram mencionadas (nota 1, depois nota 2,
# etc.). Nada e' "adivinhado": se a entrada nao mencionou nota nenhuma,
# ou as notas mencionadas nao tem saldo suficiente do produto, o que
# sobrar vira SEM CORRESPONDENCIA (e gera aviso) pra alguem corrigir
# na planilha - em vez de o programa puxar saldo de uma nota que
# ninguem citou.
#
# As entradas sao processadas por data de recebimento (mais antiga
# primeiro). Isso so' importa no caso raro de duas entradas mencionarem
# a MESMA nota disputando o mesmo saldo: a mais antiga leva primeiro.
#
# Avisos: so' avisamos "nota nao encontrada" quando o numero da NF nao
# existe em NENHUMA saida. Uma nota que existe mas nao tem determinado
# produto e' normal quando a entrada tem varios produtos e varias notas
# (cada nota cobre um pedaco) - isso NAO gera aviso; so' avisamos se, no
# fim, sobrar quantidade sem alocar.
# ----------------------------------------------------------------------
def conciliar(saidas, entradas):
    saldo_map = {}
    nfs_existentes = set()
    for s in saidas:
        nfs_existentes.add(s.nf)
        for produto, qtd in s.produtos.items():
            saldo_map[(s.nf, produto)] = SaldoNF(
                nf=s.nf, serie=s.serie, data=s.data,
                fornecedor=s.fornecedor, produto=produto, enviado=qtd,
                tipo=s.tipo,
            )

    alocacoes = []
    avisos = []

    entradas_ordenadas = sorted(
        entradas, key=lambda e: (e.data is None, e.data or datetime.min)
    )

    for e in entradas_ordenadas:
        ref = f"Entrada linha {e.linha} (recebimento {e.nota_recebimento or '-'})"

        # avisos por NOTA (uma vez por entrada, nao por produto)
        for posicao, nota in enumerate(e.notas_mencionadas, start=1):
            if nota not in nfs_existentes:
                avisos.append(
                    f"{ref}: nota mencionada {posicao} ('{nota}') nao existe "
                    f"em nenhuma saida."
                )
                continue
            # confere fornecedor/data usando qualquer saida dessa nota
            origem = next((v for (nf, _), v in saldo_map.items() if nf == nota), None)
            if origem is None:
                continue
            if origem.fornecedor != e.fornecedor:
                avisos.append(
                    f"{ref}: fornecedor '{e.fornecedor}' diverge do fornecedor "
                    f"'{origem.fornecedor}' da nota mencionada {posicao} ('{nota}'). "
                    f"Confira os dados."
                )
            if origem.data and e.data and e.data < origem.data:
                avisos.append(
                    f"[VALIDACAO] {ref}: data de entrada ({e.data:%d/%m/%Y}) e "
                    f"anterior a data de saida da nota mencionada {posicao} "
                    f"'{nota}' ({origem.data:%d/%m/%Y}). Confira as datas."
                )
            if e.tipo and origem.tipo and normalizar(e.tipo) != normalizar(origem.tipo):
                avisos.append(
                    f"{ref}: tipo '{e.tipo}' diverge do tipo '{origem.tipo}' "
                    f"da nota mencionada {posicao} ('{nota}'). Confira se e' "
                    f"mesmo retorno de Retrabalho/Industrializacao/etc. dessa nota."
                )

        # alocacao por PRODUTO, so' nas notas mencionadas
        for produto, qtd_total in e.produtos.items():
            restante = qtd_total

            for posicao, nota in enumerate(e.notas_mencionadas, start=1):
                if restante <= 1e-9:
                    break
                origem = saldo_map.get((nota, produto))
                if origem is None or origem.disponivel <= 1e-9:
                    continue  # essa nota nao cobre este produto - normal, sem aviso
                usar = min(restante, origem.disponivel)
                origem.alocado += usar
                restante = round(restante - usar, 6)
                alocacoes.append(dict(
                    entrada_linha=e.linha, nota_recebimento=e.nota_recebimento,
                    data_entrada=e.data, fornecedor=e.fornecedor, produto=produto,
                    nf_saida=origem.nf, quantidade=usar,
                    origem=f"nota mencionada {posicao}",
                ))

            if restante > 1e-9:
                alocacoes.append(dict(
                    entrada_linha=e.linha, nota_recebimento=e.nota_recebimento,
                    data_entrada=e.data, fornecedor=e.fornecedor, produto=produto,
                    nf_saida=None, quantidade=restante, origem="SEM CORRESPONDENCIA",
                ))
                if not e.notas_mencionadas:
                    motivo = "nenhuma nota mencionada foi informada"
                else:
                    notas = ", ".join(repr(n) for n in e.notas_mencionadas)
                    motivo = (f"as notas mencionadas ({notas}) nao tem saldo "
                              f"suficiente desse produto")
                avisos.append(
                    f"{ref}: sobraram {restante} unidade(s) do produto '{produto}' "
                    f"sem alocar - {motivo}."
                )

    return saldo_map, alocacoes, avisos
