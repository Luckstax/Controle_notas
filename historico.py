"""
Log local (JSON) de cada execucao do script: data/hora e as contagens
principais (notas de saida, notas de entrada, avisos, alocacoes).
Serve so pra acompanhar o crescimento ao longo do tempo - e' I/O de
disco local, nao depende de rede nem da API do Sheets, por isso fica
separado de escrita.py (que so cuida de falar com o Google Sheets).

Se der qualquer problema ao salvar (disco cheio, sem permissao, etc.),
isso NUNCA deve derrubar o script principal - so avisa no console.
"""

import json
import os
from datetime import datetime

CAMINHO_HISTORICO_PADRAO = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "historico.json"
)


def _ler_historico(caminho):
    if not os.path.exists(caminho):
        return []
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            dados = json.load(f)
        if isinstance(dados, list):
            return dados
    except (json.JSONDecodeError, OSError):
        pass
    return []


def registrar_execucao(saidas, entradas, avisos, alocacoes, dry_run=False, caminho=None):
    """Adiciona uma entrada ao final do historico.json com a data/hora
    desta execucao e as contagens principais. Chame uma vez no main(),
    depois que a conciliacao ja rodou (e, se nao for dry-run, depois
    de escrever na planilha)."""
    caminho = caminho or CAMINHO_HISTORICO_PADRAO
    historico = _ler_historico(caminho)

    sem_correspondencia = sum(1 for a in alocacoes if a.get("nf_saida") is None)

    historico.append({
        "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "dry_run": dry_run,
        "notas_saida": len(saidas),
        "notas_entrada": len(entradas),
        "avisos": len(avisos),
        "alocacoes": len(alocacoes),
        "sem_correspondencia": sem_correspondencia,
    })

    try:
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(historico, f, ensure_ascii=False, indent=2)
    except OSError as erro:
        print(f"  aviso: nao consegui salvar o historico.json ({erro}).")
