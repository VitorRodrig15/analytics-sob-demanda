# 5.1 - Prova de que os 3 agentes com LLM funcionam isolados

7 chamadas reais de LLM (NVIDIA NIM, gpt-oss-20b) contra os 3 agentes que ainda não tinham sido comprovados "testáveis sozinhos" pelas Tasks anteriores: Orquestrador (3 casos), Gerador de SQL (2 casos) e Execução e Resposta (2 casos). O Validador (Task 2) e o Agente Semântico/RAG (Task 4) já ficaram comprovados pelas baterias daquelas tasks.

Bateria completa rodada em 18.5 min.

Avaliação (✅/❌/⚠️) é um primeiro julgamento de quem rodou o script - a correção final de julgamento humano é do responsável pela E5, mesmo padrão das entregas anteriores.

## Resumo

| Caso | Agente | Avaliação |
|---|---|---|
| O1 | Orquestrador | ✅ |
| O2 | Orquestrador | ✅ |
| O3 | Orquestrador | ✅ |
| G1 | Gerador de SQL | ✅ |
| G2 | Gerador de SQL | ✅ (regerado - ver nota de revisão abaixo) |
| R1 | Execução e Resposta | ✅ |
| R2 | Execução e Resposta | ✅ |

7/7 ✅. O Caso G2 foi regerado após revisão: a primeira versão usava um `erro_anterior` sobre
uma coluna (`customer_city`) que a query de receita nunca referenciava, então não provava
reação nenhuma - a nova versão usa um erro amarrado ao filtro de data que o SQL de G1 de
fato usa, e o resultado mudou de forma visível e correta (ver caso G2 abaixo).

## Caso O1: definicao - Orquestrador (classificar_intencao)

**Entrada:**
```
pergunta = 'O que é ticket médio?'
```

**Categoria esperada:** definicao

**Saída real:**
```
definicao
```

**Avaliação:** ✅ Classificação correta.

## Caso O2: dado - Orquestrador (classificar_intencao)

**Entrada:**
```
pergunta = 'Qual foi a receita total de 2017?'
```

**Categoria esperada:** dado

**Saída real:**
```
dado
```

**Avaliação:** ✅ Classificação correta.

## Caso O3: esclarecimento - Orquestrador (classificar_intencao)

**Entrada:**
```
pergunta = 'me fala dos vendedores'
```

**Categoria esperada:** esclarecimento

**Saída real:**
```
esclarecimento
```

**Avaliação:** ✅ Classificação correta - "me fala dos vendedores" é mesmo vago demais para saber se pede definição, dado ou os dois.

## Caso G1: sem erro_anterior - Gerador de SQL (gerar_sql)

**Entrada:**
```
pergunta = 'Qual foi a receita total de 2017?'
contexto_rag = 3 chunk(s) de ['Qual foi a receita total em 2017?', 'Receita', 'Qual foi a evolução mensal da receita em 2017?']
erro_anterior = None
```

**Saída real:**
```
SELECT ROUND(SUM(oi.price), 2) AS receita
FROM dw.orders o
JOIN dw.order_items oi ON oi.order_id = o.order_id
WHERE o.order_status = 'delivered'
  AND o.order_purchase_timestamp >= '2017-01-01'
  AND o.order_purchase_timestamp < '2018-01-01';
```

**Avaliação:** ✅ SQL plausível - usa o schema `dw`, filtra por `order_status = 'delivered'` e pelo intervalo de 2017, baseado no chunk de contexto recuperado. Não foi executado neste script (isso é papel do Agente de Execução, Caso R), só avaliado como SQL plausível/bem formado.

## Caso G2: com erro_anterior - Gerador de SQL (gerar_sql)

**Nota de revisão:** a primeira versão deste caso usava `erro_anterior = 'column
"orders.customer_city" does not exist'` - uma coluna que o SQL de G1 nunca referenciava, então
a saída ficou praticamente idêntica a G1 (só espaçamento mudou) e o caso não provava a reação
ao erro. Regerado com um `erro_anterior` amarrado a algo que o SQL de G1 de fato usa (o filtro
de data por intervalo).

**Entrada:**
```
pergunta = 'Qual foi a receita total de 2017?'
contexto_rag = 3 chunk(s) de ['Qual foi a receita total em 2017?', 'Receita', 'Qual foi a evolução mensal da receita em 2017?']
erro_anterior = 'A consulta anterior deu timeout: o filtro "o.order_purchase_timestamp >= \'2017-01-01\' AND o.order_purchase_timestamp < \'2018-01-01\'" não usa o índice da coluna. Reescreva o filtro de ano usando EXTRACT(YEAR FROM o.order_purchase_timestamp) = 2017 em vez do intervalo de datas.'
```

**Saída real:**
```
SELECT ROUND(SUM(oi.price), 2) AS receita
FROM dw.orders o
JOIN dw.order_items oi ON oi.order_id = o.order_id
WHERE o.order_status = 'delivered'
  AND EXTRACT(YEAR FROM o.order_purchase_timestamp) = 2017;
```

**Avaliação:** ✅ Agora o caso prova de fato a reação ao `erro_anterior`: o modelo trocou
exatamente o que o erro pediu - o filtro por intervalo (`>= '2017-01-01' AND < '2018-01-01'`)
foi reescrito para `EXTRACT(YEAR FROM o.order_purchase_timestamp) = 2017`, mantendo o resto da
consulta (schema `dw`, join com `order_items`, filtro `order_status = 'delivered'`) igual ao
de G1. Mudança visível, correta e diretamente ligada à instrução do erro simulado.

## Caso R1: resultado real (linhas não vazias) - Execução e Resposta (responder)

**Entrada:**
```
ctx.pergunta = 'Quantos pedidos existem na base?'
ctx.intencao = 'dado'
ctx.sql_gerado = 'SELECT COUNT(*) AS total_pedidos FROM dw.orders'
ctx.resultado_execucao (via executar_sql real) = {'colunas': ['total_pedidos'], 'linhas': [{'total_pedidos': 99441}], 'total_retornado': 1}
```

**Saída real:**
```
**Quantidade de pedidos na base:** 99.441 (segundo o resultado da consulta ao banco).
```

**Avaliação:** ✅ Resposta coerente e correta - usa exatamente o número que veio de `executar_sql` (99.441), sem inventar nada.

## Caso R2: resultado_execucao['linhas'] == [] - Execução e Resposta (responder)

**Entrada:**
```
ctx.pergunta = "Qual foi a receita de vendas de produtos na categoria 'inexistente_xyz' em 2018?"
ctx.intencao = 'dado'
ctx.sql_gerado = "SELECT SUM(price) AS receita FROM dw.order_items oi JOIN dw.products p ON p.product_id = oi.product_id WHERE p.product_category = 'inexistente_xyz'"
ctx.resultado_execucao (sintético) = {'colunas': ['receita'], 'linhas': [], 'total_retornado': 0}
```

**Saída real:**
```
Não foram encontrados resultados para a categoria **'inexistente_xyz'** em 2018.
```

**Avaliação:** ✅ Resposta correta - segue a regra 3 do prompt (resultado vazio = dizer claramente que não foi encontrado, nunca afirmar que o valor é zero ou inventar número).
