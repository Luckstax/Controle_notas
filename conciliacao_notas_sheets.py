"""
Conciliacao de Notas Fiscais - Saida x Entrada (retorno) - versao Google Sheets
================================================================================
"""

import argparse
import sys

from config import caminho_env_padrao, carregar_env
from planilha_io import conectar, obter_aba, ler_matriz
from leitura import ler_saidas, ler_entradas
from conciliacao import conciliar, validar_dados
from escrita import (
    ler_overrides_anteriores, ler_avisos_anteriores, ler_alocacoes_anteriores,
    contar_alocacoes_novas, contar_avisos_novos,
    escrever_alocacoes, escrever_saldo, escrever_avisos, preencher_controle,
    escrever_retorno_por_nf, escrever_resumo_fornecedor,
)
from historico import registrar_execucao


def main():
    parser = argparse.ArgumentParser(description="Concilia notas de saida e retorno direto no Google Sheets.")
    parser.add_argument("--credenciais", help="Caminho para o .json da service account (opcional; le do .env se omitido).")
    parser.add_argument("--planilha", help="URL ou ID da planilha do Google Sheets (opcional; le do .env se omitido).")
    parser.add_argument("--env", help="Caminho do arquivo credenciais.env (opcional; tem um padrao).")
    parser.add_argument("--dry-run", action="store_true",
                         help="Le a planilha real e mostra o que SERIA escrito, mas nao grava nada nela.")
    args = parser.parse_args()

    env_path = args.env or caminho_env_padrao()
    env_vals = carregar_env(env_path)

    credenciais = args.credenciais or env_vals.get("credenciais")
    planilha = args.planilha or env_vals.get("planilha")

    if not credenciais or not planilha:
        raise SystemExit(
            f"Faltam credenciais/planilha. Verifique o arquivo '{env_path}' "
            f"(precisa ter as linhas 'credenciais = \"...\"' e 'planilha = \"...\"') "
            f"ou passe --credenciais/--planilha na linha de comando."
        )

    if args.dry_run:
        print("=" * 60)
        print("MODO DRY-RUN: nada sera gravado na planilha.")
        print("=" * 60)

    print("Conectando na planilha...")
    sh = conectar(credenciais, planilha)

    print("Lendo abas Saida e Entrada...")
    saidas = ler_saidas(ler_matriz(obter_aba(sh, "Saida")))
    entradas = ler_entradas(ler_matriz(obter_aba(sh, "Entrada")))

    print(f"{len(saidas)} notas de saida, {len(entradas)} notas de entrada.")

    avisos_validacao = validar_dados(saidas, entradas)
    if avisos_validacao:
        print(f"Validacao: {len(avisos_validacao)} problema(s) de preenchimento encontrado(s) "
              f"(veja a aba Avisos apos a execucao).")

    saldo_map, alocacoes, avisos_conciliacao = conciliar(saidas, entradas)
    avisos = avisos_validacao + avisos_conciliacao

    print("Verificando ajustes manuais feitos anteriormente...")
    overrides = ler_overrides_anteriores(sh)
    if overrides:
        print(f"{len(overrides)} ajuste(s) manual(is) encontrado(s) e sera(ao) preservado(s).")

    alocacoes_anteriores = ler_alocacoes_anteriores(sh)
    avisos_anteriores = ler_avisos_anteriores(sh)

    if args.dry_run:
        sem_correspondencia = [a for a in alocacoes if a["nf_saida"] is None]
        alocacoes_novas = contar_alocacoes_novas(alocacoes, alocacoes_anteriores)
        avisos_novos = contar_avisos_novos(avisos, avisos_anteriores)
        print("\n--- RESUMO DO QUE SERIA ESCRITO (nada foi gravado) ---")
        print(f"Alocacoes: {len(alocacoes)} ({alocacoes_novas} novas desde a ultima execucao; "
              f"{len(sem_correspondencia)} SEM CORRESPONDENCIA)")
        print(f"Avisos: {len(avisos)} ({avisos_novos} novos desde a ultima execucao)")
        if avisos:
            print("\nPrimeiros avisos:")
            for a in avisos[:15]:
                print(f"  - {a}")
            if len(avisos) > 15:
                print(f"  ... e mais {len(avisos) - 15} aviso(s).")
        print("\nNenhuma aba foi alterada (modo dry-run).")
        registrar_execucao(saidas, entradas, avisos, alocacoes, dry_run=True)
        return

    print("Escrevendo resultado na planilha...")
    escrever_alocacoes(sh, alocacoes, overrides, avisos)
    escrever_saldo(sh, saldo_map, alocacoes)
    escrever_avisos(sh, avisos)
    preencher_controle(sh, saidas, entradas)
    escrever_retorno_por_nf(sh, saidas, alocacoes)
    escrever_resumo_fornecedor(sh, saidas, entradas)
    registrar_execucao(saidas, entradas, avisos, alocacoes, dry_run=False)

    alocacoes_novas = contar_alocacoes_novas(alocacoes, alocacoes_anteriores)
    avisos_novos = contar_avisos_novos(avisos, avisos_anteriores)
    print(f"OK: {len(alocacoes)} alocacoes geradas ({alocacoes_novas} novas), "
          f"{len(avisos)} avisos ({avisos_novos} novos).")
    print("Abas atualizadas: Alocacoes, Saldo por NF, Avisos, Controle, "
          "Retorno por NF e Fornecedor e Resumo por Fornecedor.")


if __name__ == "__main__":
    codigo_saida = 0
    try:
        main()
    except Exception as erro:
        print(f"\nERRO: {erro}")
        codigo_saida = 1
    finally:
        input("\nPressione Enter para fechar...")
    sys.exit(codigo_saida)
