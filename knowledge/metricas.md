# Dicionário de Métricas — Vortex Marketplace

Definições oficiais das métricas de negócio. Toda resposta do assistente deve
usar exatamente estas fórmulas e filtros. Os SQLs usam o período de jan–ago/2018
como exemplo; troque apenas as datas.

## Receita

- **Sinônimos:** faturamento de produtos, vendas, GMV de produtos, valor vendido
- **Definição:** soma do valor dos itens vendidos em pedidos entregues, **sem frete**.
- **Fórmula:** `SUM(order_items.price)`
- **Tabelas:** dw.orders, dw.order_items
- **Filtros obrigatórios:** `order_status = 'delivered'`; período por `order_purchase_timestamp`.
- **Observações:** se o usuário pedir "faturamento com frete" ou "GMV total", use `SUM(price + freight_value)`. Não use `order_payments` para receita (inclui juros de parcelamento e vouchers).

```sql
SELECT ROUND(SUM(oi.price), 2) AS receita
FROM dw.orders o
JOIN dw.order_items oi ON oi.order_id = o.order_id
WHERE o.order_status = 'delivered'
  AND o.order_purchase_timestamp >= '2018-01-01'
  AND o.order_purchase_timestamp <  '2018-09-01';
```

## Número de pedidos

- **Sinônimos:** quantidade de pedidos, volume de pedidos, total de vendas (em quantidade)
- **Definição:** quantidade de pedidos entregues no período.
- **Fórmula:** `COUNT(order_id)` em dw.orders
- **Tabelas:** dw.orders
- **Filtros obrigatórios:** `order_status = 'delivered'`; período por `order_purchase_timestamp`.
- **Observações:** se o usuário pedir "todos os pedidos" ou "pedidos feitos", remova o filtro de status e deixe isso claro na resposta.

```sql
SELECT COUNT(*) AS pedidos
FROM dw.orders o
WHERE o.order_status = 'delivered'
  AND o.order_purchase_timestamp >= '2018-01-01'
  AND o.order_purchase_timestamp <  '2018-09-01';
```

## Ticket médio

- **Sinônimos:** valor médio do pedido, AOV, average order value, ticket
- **Definição:** receita média por pedido entregue, sem frete.
- **Fórmula:** `SUM(order_items.price) / COUNT(DISTINCT order_id)`
- **Tabelas:** dw.orders, dw.order_items
- **Filtros obrigatórios:** `order_status = 'delivered'`; período por `order_purchase_timestamp`.
- **Observações:** não use `AVG(price)`: isso é o preço médio do **item**, não do pedido.

```sql
SELECT ROUND(SUM(oi.price) / COUNT(DISTINCT o.order_id), 2) AS ticket_medio
FROM dw.orders o
JOIN dw.order_items oi ON oi.order_id = o.order_id
WHERE o.order_status = 'delivered'
  AND o.order_purchase_timestamp >= '2018-01-01'
  AND o.order_purchase_timestamp <  '2018-09-01';
```

## Itens por pedido

- **Sinônimos:** tamanho médio da cesta, produtos por pedido
- **Definição:** média de itens em cada pedido entregue.
- **Fórmula:** `COUNT(*) de order_items / COUNT(DISTINCT order_id)`
- **Tabelas:** dw.orders, dw.order_items
- **Filtros obrigatórios:** `order_status = 'delivered'`; período por `order_purchase_timestamp`.

```sql
SELECT ROUND(COUNT(*)::numeric / COUNT(DISTINCT o.order_id), 2) AS itens_por_pedido
FROM dw.orders o
JOIN dw.order_items oi ON oi.order_id = o.order_id
WHERE o.order_status = 'delivered'
  AND o.order_purchase_timestamp >= '2018-01-01'
  AND o.order_purchase_timestamp <  '2018-09-01';
```

## Percentual do frete sobre a receita

- **Sinônimos:** peso do frete, frete sobre vendas, custo de frete relativo
- **Definição:** quanto o frete representa em relação à receita de produtos.
- **Fórmula:** `SUM(freight_value) / SUM(price) * 100`
- **Tabelas:** dw.orders, dw.order_items
- **Filtros obrigatórios:** `order_status = 'delivered'`; período por `order_purchase_timestamp`.
- **Observações:** o frete médio por pedido é `SUM(freight_value) / COUNT(DISTINCT order_id)`.

```sql
SELECT ROUND(SUM(oi.freight_value), 2)                          AS frete_total,
       ROUND(SUM(oi.freight_value) / COUNT(DISTINCT o.order_id), 2) AS frete_medio_pedido,
       ROUND(100 * SUM(oi.freight_value) / SUM(oi.price), 2)    AS frete_sobre_receita_pct
FROM dw.orders o
JOIN dw.order_items oi ON oi.order_id = o.order_id
WHERE o.order_status = 'delivered'
  AND o.order_purchase_timestamp >= '2018-01-01'
  AND o.order_purchase_timestamp <  '2018-09-01';
```

## Clientes únicos

- **Sinônimos:** clientes ativos, base de clientes, compradores
- **Definição:** quantidade de pessoas distintas que tiveram pedido entregue no período.
- **Fórmula:** `COUNT(DISTINCT customers.customer_unique_id)`
- **Tabelas:** dw.orders, dw.customers
- **Filtros obrigatórios:** `order_status = 'delivered'`; período por `order_purchase_timestamp`.
- **Observações:** nunca conte `customer_id`: ele muda a cada pedido e inflaria o número de clientes.

```sql
SELECT COUNT(DISTINCT c.customer_unique_id) AS clientes_unicos
FROM dw.orders o
JOIN dw.customers c ON c.customer_id = o.customer_id
WHERE o.order_status = 'delivered'
  AND o.order_purchase_timestamp >= '2018-01-01'
  AND o.order_purchase_timestamp <  '2018-09-01';
```

## Taxa de recompra

- **Sinônimos:** clientes recorrentes, fidelização, repeat rate
- **Definição:** percentual dos clientes únicos que fizeram 2 ou mais pedidos entregues no período.
- **Fórmula:** `clientes com >= 2 pedidos / clientes únicos * 100`
- **Tabelas:** dw.orders, dw.customers
- **Filtros obrigatórios:** `order_status = 'delivered'`; período por `order_purchase_timestamp`.
- **Observações:** no histórico completo a taxa é cerca de 3%: o marketplace é majoritariamente de compra única.

```sql
WITH pedidos_por_cliente AS (
    SELECT c.customer_unique_id, COUNT(*) AS pedidos
    FROM dw.orders o
    JOIN dw.customers c ON c.customer_id = o.customer_id
    WHERE o.order_status = 'delivered'
      AND o.order_purchase_timestamp < '2018-09-01'
    GROUP BY c.customer_unique_id
)
SELECT COUNT(*)                                          AS clientes,
       COUNT(*) FILTER (WHERE pedidos >= 2)              AS clientes_recorrentes,
       ROUND(100.0 * COUNT(*) FILTER (WHERE pedidos >= 2) / COUNT(*), 2) AS taxa_recompra_pct
FROM pedidos_por_cliente;
```

## Churn de clientes

- **Sinônimos:** churn, taxa de churn, perda de clientes, clientes perdidos, evasão de clientes
- **Definição:** dos clientes que compraram nos **6 meses anteriores** ao início do período analisado (a "base"), o percentual que **não comprou** dentro do período.
- **Fórmula:** `clientes da base sem pedido no período / clientes da base * 100`
- **Tabelas:** dw.orders, dw.customers
- **Filtros obrigatórios:** `order_status = 'delivered'`; cliente = `customer_unique_id`; período por `order_purchase_timestamp`.
- **Observações:** o churn fica perto de 97–99% porque quase todos os clientes compram uma única vez. Isso é característica do negócio, não erro de cálculo; explique ao usuário. Para churn por região, agrupe pela região do cliente na base. Se a pergunta falar em **vendedores, sellers ou lojistas**, use a métrica Churn de vendedores. Se disser apenas "churn", assuma clientes e informe isso na resposta.

```sql
-- Periodo analisado: 2018-06-01 a 2018-08-31 | base: 2017-12-01 a 2018-05-31
WITH base AS (
    SELECT DISTINCT c.customer_unique_id
    FROM dw.orders o
    JOIN dw.customers c ON c.customer_id = o.customer_id
    WHERE o.order_status = 'delivered'
      AND o.order_purchase_timestamp >= DATE '2018-06-01' - INTERVAL '6 months'
      AND o.order_purchase_timestamp <  DATE '2018-06-01'
),
compraram_no_periodo AS (
    SELECT DISTINCT c.customer_unique_id
    FROM dw.orders o
    JOIN dw.customers c ON c.customer_id = o.customer_id
    WHERE o.order_status = 'delivered'
      AND o.order_purchase_timestamp >= '2018-06-01'
      AND o.order_purchase_timestamp <  '2018-09-01'
)
SELECT COUNT(*)                                             AS clientes_base,
       COUNT(*) FILTER (WHERE p.customer_unique_id IS NULL) AS clientes_churn,
       ROUND(100.0 * COUNT(*) FILTER (WHERE p.customer_unique_id IS NULL) / COUNT(*), 2) AS churn_pct
FROM base b
LEFT JOIN compraram_no_periodo p ON p.customer_unique_id = b.customer_unique_id;
```

## Churn de vendedores

- **Sinônimos:** churn de sellers, churn de lojistas, vendedores perdidos, evasão de vendedores, vendedores inativos
- **Definição:** dos vendedores que venderam nos **6 meses anteriores** ao início do período analisado (a "base"), o percentual que **não vendeu** dentro do período.
- **Fórmula:** `vendedores da base sem venda no período / vendedores da base * 100`
- **Tabelas:** dw.orders, dw.order_items, dw.sellers
- **Filtros obrigatórios:** `order_status = 'delivered'`; vendedor = `order_items.seller_id`; período por `order_purchase_timestamp`.
- **Observações:** para churn por região, use `sellers.seller_region` (região do vendedor, não do cliente). Mesma janela do churn de clientes: base de 6 meses antes do período. Cerca de 95% dos vendedores ficam no Sudeste e no Sul; em regiões com poucos vendedores na base (o Norte tem 2), o percentual é instável, então mostre sempre a quantidade da base junto.

```sql
-- Periodo analisado: 2018-06-01 a 2018-08-31 | base: 2017-12-01 a 2018-05-31
WITH base AS (
    SELECT DISTINCT oi.seller_id
    FROM dw.orders o
    JOIN dw.order_items oi ON oi.order_id = o.order_id
    WHERE o.order_status = 'delivered'
      AND o.order_purchase_timestamp >= DATE '2018-06-01' - INTERVAL '6 months'
      AND o.order_purchase_timestamp <  DATE '2018-06-01'
),
venderam_no_periodo AS (
    SELECT DISTINCT oi.seller_id
    FROM dw.orders o
    JOIN dw.order_items oi ON oi.order_id = o.order_id
    WHERE o.order_status = 'delivered'
      AND o.order_purchase_timestamp >= '2018-06-01'
      AND o.order_purchase_timestamp <  '2018-09-01'
)
SELECT COUNT(*)                                     AS vendedores_base,
       COUNT(*) FILTER (WHERE v.seller_id IS NULL)  AS vendedores_churn,
       ROUND(100.0 * COUNT(*) FILTER (WHERE v.seller_id IS NULL) / COUNT(*), 2) AS churn_vendedores_pct
FROM base b
LEFT JOIN venderam_no_periodo v ON v.seller_id = b.seller_id;
```

## Tempo médio de entrega

- **Sinônimos:** prazo de entrega, lead time, dias para entregar
- **Definição:** média de dias entre a compra e a entrega ao cliente.
- **Fórmula:** `AVG(order_delivered_customer_date - order_purchase_timestamp)` em dias
- **Tabelas:** dw.orders
- **Filtros obrigatórios:** `order_status = 'delivered'` e `order_delivered_customer_date IS NOT NULL`.

```sql
SELECT ROUND(AVG(EXTRACT(EPOCH FROM (o.order_delivered_customer_date - o.order_purchase_timestamp)) / 86400)::numeric, 1)
       AS tempo_medio_entrega_dias
FROM dw.orders o
WHERE o.order_status = 'delivered'
  AND o.order_delivered_customer_date IS NOT NULL
  AND o.order_purchase_timestamp >= '2018-01-01'
  AND o.order_purchase_timestamp <  '2018-09-01';
```

## Entregas no prazo

- **Sinônimos:** OTD, on-time delivery, pontualidade, cumprimento de prazo
- **Definição:** percentual de pedidos entregues até a data estimada informada ao cliente.
- **Fórmula:** `pedidos com entrega::date <= estimada::date / pedidos entregues * 100`
- **Tabelas:** dw.orders
- **Filtros obrigatórios:** `order_status = 'delivered'` e `order_delivered_customer_date IS NOT NULL`.
- **Observações:** compare por **data** (sem hora): a data estimada é sempre meia-noite. O complemento (100 − valor) é a **taxa de atraso**.

```sql
SELECT ROUND(100.0 * AVG((o.order_delivered_customer_date::date <= o.order_estimated_delivery_date::date)::int), 2)
       AS entregas_no_prazo_pct
FROM dw.orders o
WHERE o.order_status = 'delivered'
  AND o.order_delivered_customer_date IS NOT NULL
  AND o.order_purchase_timestamp >= '2018-01-01'
  AND o.order_purchase_timestamp <  '2018-09-01';
```

## Atraso médio

- **Sinônimos:** dias de atraso, atraso na entrega
- **Definição:** média de dias além da data estimada, **considerando só os pedidos atrasados**.
- **Fórmula:** `AVG(entrega::date - estimada::date)` onde entrega > estimada
- **Tabelas:** dw.orders
- **Filtros obrigatórios:** `order_status = 'delivered'`; somente pedidos com entrega após a data estimada.

```sql
SELECT COUNT(*) AS pedidos_atrasados,
       ROUND(AVG(o.order_delivered_customer_date::date - o.order_estimated_delivery_date::date), 1) AS atraso_medio_dias
FROM dw.orders o
WHERE o.order_status = 'delivered'
  AND o.order_delivered_customer_date::date > o.order_estimated_delivery_date::date
  AND o.order_purchase_timestamp >= '2018-01-01'
  AND o.order_purchase_timestamp <  '2018-09-01';
```

## Nota média de avaliação

- **Sinônimos:** satisfação, review score, avaliação média, CSAT
- **Definição:** média das notas (1 a 5) dadas pelos clientes.
- **Fórmula:** `AVG(order_reviews.review_score)`
- **Tabelas:** dw.orders, dw.order_reviews
- **Filtros obrigatórios:** `order_status = 'delivered'`; período por `order_purchase_timestamp` do pedido.
- **Observações:** se combinar com dw.order_items, calcule a nota por pedido antes (ver regra de multiplicação de linhas).

```sql
SELECT ROUND(AVG(r.review_score), 2) AS nota_media,
       COUNT(*)                     AS avaliacoes
FROM dw.orders o
JOIN dw.order_reviews r ON r.order_id = o.order_id
WHERE o.order_status = 'delivered'
  AND o.order_purchase_timestamp >= '2018-01-01'
  AND o.order_purchase_timestamp <  '2018-09-01';
```

## Avaliações positivas e negativas

- **Sinônimos:** % satisfeitos, % insatisfeitos, detratores, promotores
- **Definição:** positivas = notas 4 e 5; negativas = notas 1 e 2; nota 3 é neutra.
- **Fórmula:** `avaliações na faixa / total de avaliações * 100`
- **Tabelas:** dw.orders, dw.order_reviews
- **Filtros obrigatórios:** `order_status = 'delivered'`; período por `order_purchase_timestamp`.

```sql
SELECT ROUND(100.0 * AVG((r.review_score >= 4)::int), 2) AS positivas_pct,
       ROUND(100.0 * AVG((r.review_score <= 2)::int), 2) AS negativas_pct
FROM dw.orders o
JOIN dw.order_reviews r ON r.order_id = o.order_id
WHERE o.order_status = 'delivered'
  AND o.order_purchase_timestamp >= '2018-01-01'
  AND o.order_purchase_timestamp <  '2018-09-01';
```

## Taxa de cancelamento

- **Sinônimos:** pedidos cancelados, cancelamentos, pedidos perdidos
- **Definição:** percentual de pedidos com status `canceled` ou `unavailable` sobre **todos** os pedidos feitos no período.
- **Fórmula:** `pedidos cancelados ou indisponíveis / todos os pedidos * 100`
- **Tabelas:** dw.orders
- **Filtros obrigatórios:** **sem** filtro de status no denominador; período por `order_purchase_timestamp`.

```sql
SELECT COUNT(*) AS pedidos_feitos,
       COUNT(*) FILTER (WHERE o.order_status IN ('canceled', 'unavailable')) AS pedidos_cancelados,
       ROUND(100.0 * COUNT(*) FILTER (WHERE o.order_status IN ('canceled', 'unavailable')) / COUNT(*), 2)
           AS taxa_cancelamento_pct
FROM dw.orders o
WHERE o.order_purchase_timestamp >= '2018-01-01'
  AND o.order_purchase_timestamp <  '2018-09-01';
```

## Vendedores ativos

- **Sinônimos:** sellers ativos, lojistas ativos, parceiros vendendo
- **Definição:** vendedores com pelo menos um item em pedido entregue no período.
- **Fórmula:** `COUNT(DISTINCT order_items.seller_id)`
- **Tabelas:** dw.orders, dw.order_items
- **Filtros obrigatórios:** `order_status = 'delivered'`; período por `order_purchase_timestamp`.

```sql
SELECT COUNT(DISTINCT oi.seller_id) AS vendedores_ativos
FROM dw.orders o
JOIN dw.order_items oi ON oi.order_id = o.order_id
WHERE o.order_status = 'delivered'
  AND o.order_purchase_timestamp >= '2018-01-01'
  AND o.order_purchase_timestamp <  '2018-09-01';
```

## Receita por vendedor

- **Sinônimos:** faturamento médio por seller, produtividade do vendedor
- **Definição:** receita dividida pelo número de vendedores ativos no período.
- **Fórmula:** `SUM(price) / COUNT(DISTINCT seller_id)`
- **Tabelas:** dw.orders, dw.order_items
- **Filtros obrigatórios:** `order_status = 'delivered'`; período por `order_purchase_timestamp`.

```sql
SELECT ROUND(SUM(oi.price) / COUNT(DISTINCT oi.seller_id), 2) AS receita_por_vendedor
FROM dw.orders o
JOIN dw.order_items oi ON oi.order_id = o.order_id
WHERE o.order_status = 'delivered'
  AND o.order_purchase_timestamp >= '2018-01-01'
  AND o.order_purchase_timestamp <  '2018-09-01';
```

## Margem de contribuição

- **Sinônimos:** margem, lucro, lucratividade, rentabilidade, custo do produto, CMV
- **Definição:** **indisponível.** O dataset não tem custo dos produtos, comissões nem despesas variáveis.
- **Fórmula:** não calculável com os dados atuais.
- **Tabelas:** nenhuma
- **Observações:** responda que a métrica não pode ser calculada e ofereça alternativas disponíveis: receita, ticket médio ou percentual do frete sobre a receita. Nunca estime ou invente custos.
