# Conciliação de Notas Fiscais — Saída x Entrada (Google Sheets)

Concilia notas fiscais de **saída** (o que foi enviado a um fornecedor)
com as notas de **entrada** (o que voltou), calculando automaticamente
de qual nota de saída cada devolução veio — direto numa planilha do
Google Sheets alimentada por dois formulários do Google Forms.

## O que o programa faz

- Lê as abas **Entrada** e **Saída** (alimentadas pelos Forms).
- Para cada devolução, tenta casar com a(s) nota(s) de saída que a
  pessoa mencionou no formulário (até 5 por resposta). Se sobrar
  quantidade, distribui pelas notas de saída mais antigas em aberto do
  mesmo fornecedor/produto (FIFO). Se ainda sobrar, marca como **SEM
  CORRESPONDENCIA** para revisão manual — isso não é necessariamente um
  erro, pode ser retorno de uma nota antiga que ainda não foi lançada.
- Gera/atualiza automaticamente estas abas:
  - **Alocacoes** — cada devolução e de qual NF de saída ela veio.
    Tem uma coluna editável ("NF Saida (final)") para ajuste manual,
    que é preservada nas execuções seguintes.
  - **Saldo por NF** — quanto ainda falta voltar de cada nota de
    saída, com prioridade (Baixa/Média/Alta) por tempo em aberto.
  - **Avisos** — lista de divergências para revisar (nota mencionada
    não encontrada, fornecedor divergente, quantidade negativa, etc.).
  - **Controle** — totais de saída x entrada por produto.
  - **Retorno por NF e Fornecedor** — quanto voltou de cada item, por
    nota de saída e fornecedor.

## Instalação

Precisa de Python 3 e das bibliotecas listadas em `requirements.txt`:

```
pip install -r requirements.txt
```

## Configuração

1. Crie uma Service Account no Google Cloud, ative a **Google Sheets
   API** e a **Google Drive API**, e baixe o arquivo `.json` de
   credenciais.
2. Compartilhe a planilha do Google Sheets com o e-mail da service
   account (campo `client_email` do `.json`) como **Editor**.
3. Crie um arquivo `credenciais.env` na mesma pasta destes scripts,
   assim:

   ```
   credenciais = "nome-do-arquivo-da-service-account.json"
   planilha = "https://docs.google.com/spreadsheets/d/SEU_ID_AQUI/edit"
   ```

   (pode ser o nome do arquivo, se ele estiver na mesma pasta, ou um
   caminho completo)

<<<<<<< HEAD
   
=======
⚠️ **Nunca suba o `credenciais.env` nem o `.json` da service account
para o GitHub** — o `.gitignore` deste repositório já ignora os dois,
mas vale conferir com `git status` antes de cada commit.

## Formatação condicional (configurar uma vez, direto na planilha)

O script escreve os **valores** (Origem, Prioridade, etc.) mas não
colore mais nada via API — isso é de propósito: colorir linha por
linha esgotava rápido a cota de escrita do Google Sheets (~60
requisições/minuto). Em vez disso, configure regras de formatação
condicional direto no Google Sheets (uma vez só, elas continuam
funcionando sozinhas daí em diante):

**Aba "Alocacoes"** — selecione `A2:J1000` → Formatar → Formatação
condicional → "A fórmula personalizada é":
- `=$I2="SEM CORRESPONDENCIA"` → fundo vermelho claro
- `=ESQUERDA($I2;4)="fifo"` → fundo amarelo claro

**Aba "Saldo por NF"** — selecione `I2:J1000` → Formatar → Formatação
condicional → "A fórmula personalizada é":
- `=$J2="Baixa"` → texto verde, negrito
- `=$J2="Media"` → texto laranja, negrito
- `=$J2="Alta"` → texto vermelho, negrito

("Concluido" e "Sem data" ficam sem regra = sem cor, de propósito.)

Confira antes se a coluna referenciada na fórmula (I ou J) bate com o
cabeçalho real da sua planilha, caso a ordem das colunas tenha mudado.

>>>>>>> c4907cd (atualização 06/08)
## Como rodar

```
python conciliacao_notas_sheets.py
```

Não precisa passar nenhum parâmetro — ele lê tudo do `credenciais.env`.
Se quiser, dá pra sobrescrever pontualmente:

```
python conciliacao_notas_sheets.py --credenciais "..." --planilha "..."
python conciliacao_notas_sheets.py --env "C:/outra/pasta/credenciais.env"
```

### Modo simulação (dry-run)

Lê a planilha real e mostra o que **seria** escrito, sem gravar nada
nela — útil pra testar mudança de regra sem sujar a planilha de
produção:

```
python conciliacao_notas_sheets.py --dry-run
```

Ao final de cada execução (normal ou dry-run), o resumo mostra também
quantas alocações e avisos são **novos** em relação à última execução,
comparando com o que já estava nas abas antes de sobrescrever.

## Estrutura dos arquivos

| Arquivo | Responsabilidade |
|---|---|
| `conciliacao_notas_sheets.py` | Ponto de entrada — argumentos de linha de comando e o fluxo principal |
| `config.py` | Leitura do `credenciais.env` |
| `planilha_io.py` | Conexão com o Google Sheets, leitura de abas, localização de colunas pelo cabeçalho, retry automático |
| `leitura.py` | Conversão das linhas de Entrada/Saída em objetos Python, apelidos de fornecedor |
| `conciliacao.py` | A lógica de alocação FIFO e as validações pré-escrita |
| `escrita.py` | Geração das abas de resultado (Alocações, Saldo por NF, Avisos, Controle, Retorno por NF e Fornecedor) |
| `modelos.py` | Estruturas de dados (`NotaSaida`, `NotaEntrada`, `SaldoNF`) |

## Colunas esperadas

**Aba Saída:** Data, número da nota fiscal, Série, Tipo, Fornecedor, e
pares de colunas "código do produto" + "quantidade [código]" para cada
item.

**Aba Entrada:** Data de recebimento, nota de recebimento, série de
recebimento, até 5 colunas "nota mencionada N" (aceita variação
"mensionada"), Tipo, Fornecedor, e os mesmos pares de produto/quantidade
da Saída.

As colunas são localizadas **pelo texto do cabeçalho** (linha 1), não
pela posição — então a ordem/letra das colunas pode mudar (ex: ao
editar o Forms) sem quebrar o script. Se por engano existir mais de uma
coluna com o mesmo cabeçalho (ex: duas colunas "Fornecedor"), o script
usa a que estiver preenchida em cada linha e avisa no console se os
valores forem conflitantes.

## Apelidos de fornecedor

Como o campo Fornecedor tem a opção "Outro" (texto livre), a mesma
empresa pode acabar escrita de formas diferentes (ex: "Sam Correia" vs
"Sam Correia Ltda"), o que quebraria o casamento entre Saída e Entrada.
Para corrigir isso, edite o dicionário `FORNECEDOR_ALIASES` no início
de `leitura.py`:

```python
FORNECEDOR_ALIASES = {
    "sam correia ltda": "sam correia",
    "high color com. e ind.": "high color",
}
```

## Limitações conhecidas

- O Google Sheets tem um limite de requisições de escrita por minuto.
  Em planilhas muito grandes, uma execução pode esbarrar nesse limite
  mesmo com o retry automático — se acontecer, espere um ou dois
  minutos e rode de novo.
- "SEM CORRESPONDENCIA" nas Alocações não é necessariamente um erro:
  costuma indicar que a aba Saída não tem (ainda) a nota de saída
  antiga que a devolução está referenciando.
