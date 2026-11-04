# B1 - Validação dos SQLs do dicionário semântico

**38 de 38 SQLs executados com sucesso** (transação somente leitura).

| Arquivo | Item | Status | Linhas | Tempo (ms) | Primeira linha |
|---|---|---|---|---|---|
| metricas.md | Receita | OK | 1 | 3615 | receita=7218125.12 |
| metricas.md | Número de pedidos | OK | 1 | 43 | pedidos=52783 |
| metricas.md | Ticket médio | OK | 1 | 237 | ticket_medio=136.75 |
| metricas.md | Itens por pedido | OK | 1 | 140 | itens_por_pedido=1.14 |
| metricas.md | Percentual do frete sobre a receita | OK | 1 | 168 | frete_total=1233459.65, frete_medio_pedido=23.37, frete_sobre_receita_pct=17.09 |
| metricas.md | Clientes únicos | OK | 1 | 875 | clientes_unicos=51612 |
| metricas.md | Taxa de recompra | OK | 1 | 251 | clientes=93358, clientes_recorrentes=2801, taxa_recompra_pct=3.00 |
| metricas.md | Churn de clientes | OK | 1 | 351 | clientes_base=38838, clientes_churn=38578, churn_pct=99.33 |
| metricas.md | Churn de vendedores | OK | 1 | 191 | vendedores_base=1856, vendedores_churn=607, churn_vendedores_pct=32.70 |
| metricas.md | Tempo médio de entrega | OK | 1 | 78 | tempo_medio_entrega_dias=12.1 |
| metricas.md | Entregas no prazo | OK | 1 | 36 | entregas_no_prazo_pct=92.27 |
| metricas.md | Atraso médio | OK | 1 | 32 | pedidos_atrasados=4078, atraso_medio_dias=9.9 |
| metricas.md | Nota média de avaliação | OK | 1 | 433 | nota_media=4.14, avaliacoes=52678 |
| metricas.md | Avaliações positivas e negativas | OK | 1 | 66 | positivas_pct=78.58, negativas_pct=13.38 |
| metricas.md | Taxa de cancelamento | OK | 1 | 28 | pedidos_feitos=53991, pedidos_cancelados=460, taxa_cancelamento_pct=0.85 |
| metricas.md | Vendedores ativos | OK | 1 | 173 | vendedores_ativos=2330 |
| metricas.md | Receita por vendedor | OK | 1 | 171 | receita_por_vendedor=3097.91 |
| exemplos_sql.json | ex01 - Qual foi a receita total em 2017? | OK | 1 | 60 | receita=5962902.01 |
| exemplos_sql.json | ex02 - Quantos pedidos foram entregues no último mês? | OK | 1 | 7 | pedidos_entregues=6351 |
| exemplos_sql.json | ex03 - Qual o ticket médio deste ano? | OK | 1 | 175 | ticket_medio=136.75 |
| exemplos_sql.json | ex04 - Qual o tempo médio de entrega no último trimestre? | OK | 1 | 22 | tempo_medio_entrega_dias=8.6 |
| exemplos_sql.json | ex05 - Quantos pedidos tivemos na Black Friday de 2017? | OK | 1 | 7 | pedidos_feitos=1176, pedidos_entregues=1147 |
| exemplos_sql.json | ex06 - Compare a receita do Sudeste com a do Nordeste em 2018. | OK | 2 | 408 | regiao=Sudeste, receita=4786465.60, pedidos=36803 |
| exemplos_sql.json | ex07 - Como foi a receita de 2018 em relação a 2017? | OK | 2 | 234 | ano=2017, receita_jan_ago=2993456.13, variacao_pct=None |
| exemplos_sql.json | ex08 - Qual o ticket médio por forma de pagamento? | OK | 4 | 984 | forma_pagamento=credit_card, pedidos=74275, ticket_medio=142.44 |
| exemplos_sql.json | ex09 - Qual o percentual de entregas no prazo por região? | OK | 5 | 145 | regiao=Nordeste, pedidos_entregues=9044, entregas_no_prazo_pct=87.28 |
| exemplos_sql.json | ex10 - Qual o peso do frete sobre a receita em cada região? | OK | 5 | 201 | regiao=Norte, receita=327074.95, frete=74264.12 |
| exemplos_sql.json | ex11 - Como evoluiu o número de pedidos mês a mês em 2018? | OK | 8 | 32 | mes=2018-01-01, pedidos=7069 |
| exemplos_sql.json | ex12 - Qual foi a evolução mensal da receita em 2017? | OK | 12 | 97 | mes=2017-01-01, receita=111798.36 |
| exemplos_sql.json | ex13 - Como a nota média de avaliação variou ao longo dos meses? | OK | 20 | 179 | mes=2017-01-01, avaliacoes=748, nota_media=4.21 |
| exemplos_sql.json | ex14 - O tempo de entrega melhorou ao longo dos trimestres? | OK | 6 | 155 | trimestre=2017-T1, pedidos=4949, tempo_medio_entrega_dias=13.0 |
| exemplos_sql.json | ex15 - Como evoluiu a taxa de cancelamento por mês? | OK | 20 | 95 | mes=2017-01-01, pedidos_feitos=800, taxa_cancelamento_pct=1.63 |
| exemplos_sql.json | ex16 - Quais são as 10 categorias com maior receita? | OK | 10 | 819 | categoria=beleza_saude, receita=1233131.72, pedidos=8647 |
| exemplos_sql.json | ex17 - Quem foram os 10 vendedores com maior receita em 2018? | OK | 10 | 948 | seller_id=4869f7a5dfa277a7dca6462dcf3b52b2, cidade=guariba, uf=SP |
| exemplos_sql.json | ex18 - Quais estados têm mais atrasos nas entregas? | OK | 10 | 204 | uf=AL, pedidos_entregues=397, pedidos_atrasados_pct=21.41 |
| exemplos_sql.json | ex19 - Quais categorias têm a pior avaliação dos clientes? | OK | 10 | 3591 | categoria=moveis_escritorio, pedidos_avaliados=1244, nota_media=3.64 |
| exemplos_sql.json | ex20 - Qual foi a taxa de churn por região no último trimestre? | OK | 5 | 289 | regiao=Norte, clientes_base=651, clientes_churn=649 |
| exemplos_sql.json | ex21 - Qual foi a taxa de churn de vendedores por região no último trimestre? | OK | 5 | 149 | regiao=Norte, vendedores_base=2, vendedores_churn=2 |
