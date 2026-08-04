"""
Estruturas de dados usadas pelo restante do programa: uma nota de
saida, uma nota de entrada (retorno) e o saldo em aberto de uma NF
de saida por produto.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class NotaSaida:
    linha: int
    data: datetime
    nf: str
    serie: str
    tipo: str
    fornecedor: str
    produtos: dict


@dataclass
class NotaEntrada:
    linha: int
    data: datetime
    nota_recebimento: str
    serie_recebimento: str
    notas_mencionadas: tuple  # ate 5 notas mencionadas, em ordem
    tipo: str
    fornecedor: str
    produtos: dict


@dataclass
class SaldoNF:
    nf: str
    serie: str
    data: datetime
    fornecedor: str
    produto: str
    enviado: float
    alocado: float = 0.0

    @property
    def disponivel(self):
        return round(self.enviado - self.alocado, 6)
