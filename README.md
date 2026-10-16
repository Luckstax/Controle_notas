# Conciliação de Notas Fiscais — Saída x Entrada (Google Sheets)

Concilia notas fiscais de **saída** (o que foi enviado a um fornecedor)
com as notas de **entrada** (o que voltou), calculando automaticamente
de qual nota de saída cada devolução veio — direto numa planilha do
Google Sheets alimentada por dois formulários do Google Forms.

## O que o programa faz

- Lê as abas **Entrada** e **Saída** (alimentadas pelos Forms).
- Para cada devolução, casa com a(s) nota(s) de saída que a pessoa
  mencionou no formulário (até 5 por resposta, na ordem preenchida). O
  programa **não tenta adivinhar** de qual NF uma devolução veio: só
  aloca onde a pessoa disse que veio (não há mais distribuição
  automática por FIFO/nota mais antiga). Se a quantidade mencionada não
  for suficiente, ou nenhuma nota tiver sido mencionada, o que sobrar
  vira **SEM CORRESPONDENCIA** para revisão manual — isso não é
  necessariamente um erro, pode ser retorno de uma nota antiga que
  ainda não foi lançada, ou a pessoa pode ter esquecido de preencher a
  nota mencionada no formulário.
- Gera/atualiza automaticamente estas abas:
  - **Alocacoes** — cada devolução e de qual NF de saída ela veio.
    Tem uma coluna editável ("NF Saida (final)") para ajuste manual,
    que é preservada nas execuções seguintes.
  - **Saldo por NF** — quanto ainda falta voltar de cada nota de
    saída, com prioridade (Baixa/Média/Alta) por tempo em aberto.
  - **Avisos** — lista de divergências para revisar (nota mencionada
    não encontrada, fornecedor divergente, quantidade negativa, etc.).
  - **Controle** — totais de saída x entrada por produto.
  - **Resumo por Fornecedor** — total enviado x total retornado por
    (fornecedor, produto), somado direto, ignorando a NF específica.
    Diferença negativa = já voltou mais do que foi enviado segundo o
    que está lançado — sinal de nota de saída faltando ou lançada
    errada.
  - **Recebido por Dia** — quanto foi recebido (Entrada) de cada tipo de
    peça, de cada fornecedor, em cada dia (uma linha por data + fornecedor,
    uma coluna por produto e um total). Soma direto das entradas pela data
    de recebimento, sem depender da conciliação com as notas de saída.
    Para a peça 02485-I há ainda duas colunas comparando o recebido do dia
    com a meta diária do High Color (400): recebido − meta, em peças e em %
    (negativo = faltou entregar). Só preenche se houve entrada de 02485-I
    naquele dia; Sam Correia fica em branco. As metas ficam em
    `METAS_DIARIAS` no `escrita.py`.
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

(A versão antiga do script tinha FIFO automático e uma regra amarela
pra isso; o FIFO foi removido — agora a coluna Origem só tem "nota
mencionada N" ou "SEM CORRESPONDENCIA" — então essa regra amarela não
se aplica mais e pode ser apagada se ainda existir na sua planilha.)

**Aba "Saldo por NF"** — selecione `J2:J1000` → Formatar → Formatação
condicional → "A fórmula personalizada é":
- `=$J2="Baixa"` → texto verde, negrito
- `=$J2="Media"` → texto laranja, negrito
- `=$J2="Alta"` → texto vermelho, negrito

("Concluido" e "Sem data" ficam sem regra = sem cor, de propósito.)

Confira antes se a coluna referenciada na fórmula bate com o cabeçalho
real da sua planilha, caso a ordem das colunas tenha mudado (a coluna
"Tipo" foi adicionada depois, então Prioridade pode não estar mais na
mesma letra que era antes).

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
| `escrita.py` | Geração das abas de resultado (Alocações, Saldo por NF, Avisos, Controle, Retorno por NF e Fornecedor, Resumo por Fornecedor) |
| `historico.py` | Log local (`historico.json`) com data/hora e contagens de cada execução |
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
