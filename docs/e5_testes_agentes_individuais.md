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
| G2 | Gerador de SQL | ⚠️ (ver nota abaixo) |
| R1 | Execução e Resposta | ✅ |
| R2 | Execução e Resposta | ✅ |

6/7 ✅, 1/7 ⚠️. O único ponto de atenção é o Caso G2: o `erro_anterior` simulado não era aplicável à query testada, então o caso não chega a provar a reação ao erro pedida pelo brief (ver nota no caso).

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

**Entrada:**
```
pergunta = 'Qual foi a receita total de 2017?'
contexto_rag = 3 chunk(s) de ['Qual foi a receita total em 2017?', 'Receita', 'Qual foi a evolução mensal da receita em 2017?']
erro_anterior = 'column "orders.customer_city" does not exist'
```

**Saída real:**
```
SELECT ROUND(SUM(oi.price), 2) AS receita
FROM dw.orders o
JOIN dw.order_items oi ON oi.order_id = o.order_id
WHERE o.order_status = 'delivered'
  AND o.order_purchase_timestamp >= '2017-01-01'
  AND o.order_purchase_timestamp <  '2018-01-01';
```

**Avaliação:** ⚠️ SQL ainda plausível, mas o caso não comprova bem a reação ao erro: o SQL de G1 já não usava `customer_city`, então o `erro_anterior` simulado (sobre uma coluna que a query nem referenciava) não tinha como provocar uma correção visível - a saída ficou praticamente idêntica a G1 (só espaçamento mudou). Para provar de fato que o prompt reage a `erro_anterior`, o erro precisaria ser sobre algo que a consulta original realmente usasse (ex.: um erro de sintaxe ou de coluna que o G1 tivesse cometido). O comportamento observado (ignorar um erro que não se aplica) é razoável, mas não é a prova pretendida pelo brief.

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
