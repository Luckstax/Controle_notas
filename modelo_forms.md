# Modelo dos formulários (Google Forms)

Este projeto espera **dois** Google Forms separados, cada um enviando
as respostas para uma aba diferente na mesma planilha (`Saida` e
`Entrada`). O script localiza as colunas pelo **texto do cabeçalho**,
não pela posição — então a ordem das perguntas abaixo é só sugestão,
o que importa é o texto de cada pergunta bater com o que está aqui.

Troque `PRODUTO-A`, `PRODUTO-B`, etc. pelos códigos reais dos seus
produtos — repita o bloco "Produto" para cada item que você controla.

## Formulário 1 — Saída

Configure o destino das respostas para a aba **"Saida"** da planilha.

| # | Pergunta | Tipo |
|---|---|---|
| 1 | Data de envio | Data |
| 2 | numero da nota fiscal | Resposta curta |
| 3 | Serie | Resposta curta |
| 4 | Tipo | Múltipla escolha (+ "Outro") |
| 5 | Fornecedor | Múltipla escolha (+ "Outro" — veja nota abaixo) |
| 6 | PRODUTO-A | Resposta curta *(nome do produto, so' pra referencia visual)* |
| 7 | quantidade PRODUTO-A | Resposta curta (numérico) |
| 8 | PRODUTO-B | Resposta curta |
| 9 | quantidade PRODUTO-B | Resposta curta (numérico) |
| ... | *(repita o par produto/quantidade pra cada item)* | |

O Forms sempre adiciona a coluna **"Carimbo de data/hora"** sozinho no
início — não precisa criar essa pergunta, ela já vem de fábrica.

## Formulário 2 — Entrada

Configure o destino das respostas para a aba **"Entrada"** da planilha.

| # | Pergunta | Tipo |
|---|---|---|
| 1 | Data de recebimento | Data |
| 2 | nota de recebimento | Resposta curta |
| 3 | Serie de recebimento | Resposta curta |
| 4 | nota mencionada 1 | Resposta curta |
| 5 | Outra nota mencionada? | Múltipla escolha (Sim/Não) — usada só como gatilho de lógica de seção do Forms, o script ignora essa coluna |
| 6 | nota mencionada 2 | Resposta curta (seção que só aparece se a pergunta 5 = "Sim") |
| 7 | Outra nota mencionada? | Múltipla escolha (Sim/Não) |
| 8 | nota mencionada 3 | Resposta curta |
| 9 | Outra nota mencionada? | Múltipla escolha (Sim/Não) |
| 10 | nota mencionada 4 | Resposta curta |
| 11 | Outra nota mencionada? | Múltipla escolha (Sim/Não) |
| 12 | nota mencionada 5 | Resposta curta |
| 13 | Tipo | Múltipla escolha (+ "Outro") |
| 14 | Fornecedor | Múltipla escolha (+ "Outro") |
| 15+ | PRODUTO-A / quantidade PRODUTO-A / ... | mesmo padrão da Saída |

O script aceita **quantas colunas "nota mencionada N" existirem** — não
tem limite fixo de 5, é só o padrão usado aqui. Pra adicionar uma 6ª,
basta criar uma nova pergunta "nota mencionada 6" no Forms, o script
encontra ela sozinho pelo cabeçalho.

## Duas dicas importantes

1. **A opção "Outro" em Tipo/Fornecedor é texto livre.** Isso é
   conveniente, mas pode gerar grafias diferentes pra mesma empresa
   (ex: "Sam Correia" vs "Sam Correia Ltda"). O script tem um
   dicionário de apelidos (`FORNECEDOR_ALIASES`, em `leitura.py`) pra
   corrigir isso sem precisar travar o campo no Forms — veja o
   `README.md` principal.
2. **Evite duplicar o cabeçalho "Fornecedor"** (ou qualquer outro) na
   planilha de respostas ao editar o Forms depois de já ter respostas
   antigas — se acontecer, o script já sabe lidar com isso (usa a
   coluna que tiver valor preenchido em cada linha), mas o ideal é
   revisar a planilha depois de qualquer edição no Forms pra
   confirmar que não sobrou cabeçalho repetido.
