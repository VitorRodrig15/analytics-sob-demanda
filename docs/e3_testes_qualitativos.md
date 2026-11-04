# 3.5 - Testes qualitativos do pipeline RAG

12 perguntas (acima do mínimo de 10 do entregável) rodadas pelo pipeline end-to-end
(3.3), cobrindo as 4 intenções do dicionário (agregação, comparação, tendência,
ranking) mais regra de negócio, métrica indisponível, segurança e descrição de
tabela. Respostas brutas em `docs/e3_testes_qualitativos.jsonl`.

Cada resposta foi avaliada em 3 critérios, como pede o entregável: **correção**
(o conteúdo está certo?), **relevância do contexto** (os chunks recuperados
eram os certos?) e **citação de fontes** (a resposta aponta de onde veio a
informação?).

## Resumo

| Critério | Resultado |
|---|---|
| Contexto relevante | **12/12 (100%)** |
| Citou a fonte (completo ou parcial) | **11/12 (92%)** |
| Resposta correta (completa ou parcial) | **11/12 (92%)**, sendo 10 completas e 1 parcial |
| Números inventados | **0/12** — nunca aconteceu |

## Tabela por pergunta

| # | Categoria | Pergunta | Contexto | Citou fonte | Correção |
|---|---|---|---|---|---|
| 1 | agregação | Receita total em 2017 | ✅ | ✅ | ✅ Correta |
| 2 | agregação | Ticket médio deste ano | ✅ | ✅ | ❌ **Incorreta** — usou 2026 como "ano atual" |
| 3 | comparação | Receita Sudeste x Nordeste | ✅ | ✅ | ✅ Correta |
| 4 | tendência | Evolução de pedidos em 2018 | ✅ | ❌ Não citou | ✅ Correta |
| 5 | ranking | Categorias com mais receita | ✅ | ⚠️ Parcial (1 de 2 fontes) | ✅ Correta |
| 6 | ranking | Churn de vendedores por região | ✅ | ✅ | ⚠️ **Parcial** — SQL com ano 2023, resposta cortada |
| 7 | regra | Como calcular churn de clientes | ✅ | ✅ | ✅ Correta |
| 8 | indisponível | Margem de lucro por categoria | ✅ | ✅ | ✅ Correta |
| 9 | segurança | Pode apagar/alterar dados? | ✅ | ✅ | ✅ Correta |
| 10 | regra | O que é "último trimestre" | ✅ | ✅ | ✅ Correta |
| 11 | tabela | O que tem em order_payments | ✅ | ✅ | ✅ Correta |
| 12 | agregação | Clientes satisfeitos com entrega? | ✅ | ✅ | ✅ Correta |

## O que funcionou bem

- **Nunca inventou um número.** Em toda pergunta que pedia um valor exato (receita,
  ticket médio, churn...), o agente explicou a fórmula e disse que ainda não tem
  acesso de execução ao banco — o comportamento esperado nesta etapa (o pipeline
  ainda não roda SQL de verdade, só explica o dicionário; isso é tarefa do Agente
  Gerador de SQL e do Agente de Execução, na E4/E5).
- **Margem de contribuição (pergunta 8):** recusou calcular, citou a fonte e ofereceu
  3 alternativas reais do dicionário — exatamente a regra 4 do system prompt.
- **Segurança (pergunta 9):** recusou com precisão, listando os comandos proibidos
  do jeito que estão na regra de negócio, sem rodeio.
- **"Último trimestre" (pergunta 10):** resposta mais limpa de toda a bateria —
  curta, com a data certa (01/06 a 31/08/2018) e a fonte citada.
- **Churn de clientes (pergunta 7):** citou a fonte 5 vezes ao longo da resposta e
  incluiu sozinho a observação de que ~97-99% é esperado, não um erro.

## Problemas encontrados

### 1. Datas relativas erradas quando a regra de datas não é recuperada (perguntas 2 e 6)

O achado mais importante da bateria. Em duas perguntas, o agente **não usou a data
de referência fixa do projeto (31/08/2018)**:
- Na pergunta 2 ("ticket médio deste ano"), ele assumiu **2026** como ano corrente.
- Na pergunta 6 (churn de vendedores), o SQL gerado usou **abril de 2023** em vez
  de junho de 2018.

A causa: com `k=3`, quando a pergunta já tem 2-3 chunks muito parecidos sobre a
própria métrica, o chunk da regra "Datas relativas" (que tem a data de referência)
não entra no top 3 e o modelo preenche a lacuna com a data real de hoje.

**Correção que recomendo:** colocar a data de referência (31/08/2018) direto no
system prompt, como um fato fixo que não depende da busca. Isso garante que ela
esteja sempre disponível, não importa quais chunks foram recuperados.

### 2. Resposta cortada por falta de tokens (pergunta 6)

A resposta da pergunta 6 terminou no meio do SQL (`WHERE v.seller`) porque bateu no
limite de `max_tokens=800`. Isso reforça o achado do 3.2: perguntas que geram SQL
complexo (CTEs com múltiplas etapas) precisam de mais espaço.

### 3. Citação de fonte inconsistente (perguntas 4 e 5)

A regra 3 do prompt (citar a fonte) nem sempre é seguida à risca — na pergunta 4
não apareceu nenhuma citação, e na 5 só uma das duas fontes usadas foi citada.

### 4. SQL exposto sem ter sido pedido (regra 5 do prompt)

7 das 12 respostas incluíram um bloco de SQL, mesmo a regra 5 dizendo para só
mostrar SQL se o usuário pedir explicitamente. Nenhuma das 12 perguntas pedia o
SQL. Isso não é incorreto — o SQL ajuda o usuário técnico — mas é uma regra do
prompt que não está sendo seguida à risca, e vale endurecer o texto.

## Recomendações para a próxima iteração do prompt (3.4)

1. Incluir a data de referência (2018-08-31) direto no system prompt, não só no
   dicionário.
2. Aumentar `max_tokens` para 1200 em perguntas que envolvem SQL mais longo.
3. Reforçar a regra 3 (citação obrigatória, não opcional) e a regra 5 (SQL só
   quando pedido), deixando menos espaço para o modelo "decidir" seguir ou não.

## Correção aplicada e reteste (mesmo dia)

As 3 recomendações acima foram aplicadas no `scripts/prompts.py` (data fixa no
system prompt + regras 3 e 5 reescritas como obrigatórias) e no
`scripts/rag_pipeline.py` (`max_tokens` 800 → 1200). As 2 perguntas que tinham
falhado foram refeitas com o prompt corrigido. Resultado em
`docs/e3_reteste_correcao.jsonl`:

| # | Pergunta | Antes da correção | Depois da correção |
|---|---|---|---|
| 2 | Ticket médio deste ano | Usou **2026** como ano atual | ✅ Usou **2018 (01/01–31/08)**, citando a fonte corretamente |
| 6 | Churn de vendedores por região | SQL com data **2023**, resposta cortada no meio | ✅ Usou **01/06–31/08/2018** (base 01/12/2017–31/05/2018), 5 citações de fonte, resposta completa — e desta vez só ofereceu o SQL em vez de despejá-lo sem pedido |

**O problema de datas foi resolvido nas 2 perguntas.** A citação de fonte também
melhorou bastante (de 1 citação solta para várias, uma por etapa do raciocínio).
A regra de "não mostrar SQL sem pedir" melhorou parcialmente: a pergunta 6 passou
a só oferecer a consulta ("se precisar, basta pedir"), mas a pergunta 2 ainda
incluiu um bloco de SQL sem ter sido solicitado — um modelo de linguagem não
segue uma regra de prompt com 100% de disciplina, então isso fica registrado como
um comportamento a observar (não corrigido por completo) nas próximas entregas,
quando o Agente Validador (E5) vai filtrar isso de forma determinística, não
apenas pedir educadamente ao modelo.
