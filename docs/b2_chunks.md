# B2 - Chunks do dicionário semântico

**61 chunks** gerados por unidade semântica. Tokens do texto de busca medidos com tokenizador e5-large-v2; limite do modelo: 512. Chunks acima do limite: **0**.

| doc_type | Fonte | Chunks | Tokens mín. | Tokens médio | Tokens máx. |
|---|---|---|---|---|---|
| metric | metricas.md | 18 | 141 | 197 | 351 |
| business_rule | regras_negocio.md | 13 | 70 | 132 | 286 |
| table_schema | tabelas.md | 8 | 239 | 318 | 399 |
| sql_example | exemplos_sql.json | 22 | 36 | 44 | 53 |

## Exemplo de chunk: Ticket médio

**Texto de busca** (vira embedding, sem SQL):

```text
Métrica: Ticket médio
- **Sinônimos:** valor médio do pedido, AOV, average order value, ticket
- **Definição:** receita média por pedido entregue, sem frete.
- **Fórmula:** `SUM(order_items.price) / COUNT(DISTINCT order_id)`
- **Tabelas:** dw.orders, dw.order_items
- **Filtros obrigatórios:** `order_status = 'delivered'`; período por `order_purchase_timestamp`.
- **Observações:** não use `AVG(price)`: isso é o preço médio do **item**, não do pedido.
```

**Conteúdo** (entregue ao agente, com SQL):

````text
Métrica: Ticket médio

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
````

**Metadados:**

```json
{
  "id": "metric:ticket-medio",
  "doc_type": "metric",
  "source": "metricas.md",
  "title": "Ticket médio",
  "tags": [
    "dw.order_items",
    "dw.orders",
    "ticket-medio"
  ],
  "metadata": {
    "synonyms": [
      "valor médio do pedido",
      "AOV",
      "average order value",
      "ticket"
    ],
    "tables": [
      "dw.orders",
      "dw.order_items"
    ],
    "available": true
  },
  "search_tokens": 184,
  "created_at": "2026-10-28T18:59:24+00:00"
}
```

## Todos os chunks

| id | Título | Tokens de busca | Tamanho do conteúdo (caracteres) |
|---|---|---|---|
| `metric:receita` | Receita | 225 | 813 |
| `metric:numero-de-pedidos` | Número de pedidos | 199 | 674 |
| `metric:ticket-medio` | Ticket médio | 184 | 744 |
| `metric:itens-por-pedido` | Itens por pedido | 141 | 649 |
| `metric:percentual-do-frete-sobre-a-receita` | Percentual do frete sobre a receita | 192 | 963 |
| `metric:clientes-unicos` | Clientes únicos | 186 | 758 |
| `metric:taxa-de-recompra` | Taxa de recompra | 188 | 1079 |
| `metric:churn-de-clientes` | Churn de clientes | 351 | 1992 |
| `metric:churn-de-vendedores` | Churn de vendedores | 350 | 1944 |
| `metric:tempo-medio-de-entrega` | Tempo médio de entrega | 147 | 753 |
| `metric:entregas-no-prazo` | Entregas no prazo | 217 | 911 |
| `metric:atraso-medio` | Atraso médio | 158 | 785 |
| `metric:nota-media-de-avaliacao` | Nota média de avaliação | 190 | 800 |
| `metric:avaliacoes-positivas-e-negativas` | Avaliações positivas e negativas | 168 | 767 |
| `metric:taxa-de-cancelamento` | Taxa de cancelamento | 163 | 840 |
| `metric:vendedores-ativos` | Vendedores ativos | 146 | 643 |
| `metric:receita-por-vendedor` | Receita por vendedor | 148 | 677 |
| `metric:margem-de-contribuicao` | Margem de contribuição | 196 | 492 |
| `business_rule:periodo-confiavel-dos-dados` | Período confiável dos dados | 136 | 373 |
| `business_rule:datas-relativas-ultimo-mes-ultimo-trimestre` | Datas relativas ("último mês", "último trimestre") | 286 | 676 |
| `business_rule:comparacao-entre-anos` | Comparação entre anos | 70 | 194 |
| `business_rule:status-do-pedido` | Status do pedido | 102 | 337 |
| `business_rule:data-de-referencia-do-pedido` | Data de referência do pedido | 90 | 253 |
| `business_rule:identificacao-do-cliente` | Identificação do cliente | 90 | 239 |
| `business_rule:receita-frete-e-pagamentos` | Receita, frete e pagamentos | 135 | 364 |
| `business_rule:multiplicacao-de-linhas-em-joins` | Multiplicação de linhas em JOINs | 128 | 360 |
| `business_rule:regiao` | Região | 180 | 396 |
| `business_rule:geolocalizacao` | Geolocalização | 123 | 336 |
| `business_rule:categorias-de-produto` | Categorias de produto | 103 | 293 |
| `business_rule:metricas-indisponiveis` | Métricas indisponíveis | 112 | 297 |
| `business_rule:seguranca-e-boas-praticas-de-sql` | Segurança e boas práticas de SQL | 156 | 433 |
| `table_schema:dw.orders-pedidos` | dw.orders — pedidos | 399 | 1049 |
| `table_schema:dw.order-items-itens-dos-pedidos` | dw.order_items — itens dos pedidos | 350 | 847 |
| `table_schema:dw.order-payments-pagamentos` | dw.order_payments — pagamentos | 288 | 731 |
| `table_schema:dw.order-reviews-avaliacoes` | dw.order_reviews — avaliações | 318 | 790 |
| `table_schema:dw.customers-clientes` | dw.customers — clientes | 308 | 778 |
| `table_schema:dw.sellers-vendedores` | dw.sellers — vendedores | 239 | 574 |
| `table_schema:dw.products-produtos` | dw.products — produtos | 387 | 987 |
| `table_schema:dw.geolocation-geolocalizacao-por-cep` | dw.geolocation — geolocalização por CEP | 256 | 634 |
| `sql_example:ex01` | Qual foi a receita total em 2017? | 37 | 436 |
| `sql_example:ex02` | Quantos pedidos foram entregues no último mês? | 46 | 473 |
| `sql_example:ex03` | Qual o ticket médio deste ano? | 36 | 500 |
| `sql_example:ex04` | Qual o tempo médio de entrega no último trimestre? | 47 | 622 |
| `sql_example:ex05` | Quantos pedidos tivemos na Black Friday de 2017? | 43 | 641 |
| `sql_example:ex06` | Compare a receita do Sudeste com a do Nordeste em 2018. | 50 | 776 |
| `sql_example:ex07` | Como foi a receita de 2018 em relação a 2017? | 40 | 960 |
| `sql_example:ex08` | Qual o ticket médio por forma de pagamento? | 38 | 892 |
| `sql_example:ex09` | Qual o percentual de entregas no prazo por região? | 46 | 746 |
| `sql_example:ex10` | Qual o peso do frete sobre a receita em cada região? | 53 | 844 |
| `sql_example:ex11` | Como evoluiu o número de pedidos mês a mês em 2018? | 48 | 536 |
| `sql_example:ex12` | Qual foi a evolução mensal da receita em 2017? | 41 | 583 |
| `sql_example:ex13` | Como a nota média de avaliação variou ao longo dos meses? | 46 | 702 |
| `sql_example:ex14` | O tempo de entrega melhorou ao longo dos trimestres? | 44 | 930 |
| `sql_example:ex15` | Como evoluiu a taxa de cancelamento por mês? | 40 | 690 |
| `sql_example:ex16` | Quais são as 10 categorias com maior receita? | 38 | 640 |
| `sql_example:ex17` | Quem foram os 10 vendedores com maior receita em 2018? | 40 | 873 |
| `sql_example:ex18` | Quais estados têm mais atrasos nas entregas? | 48 | 1119 |
| `sql_example:ex19` | Quais categorias têm a pior avaliação dos clientes? | 44 | 1133 |
| `sql_example:ex20` | Qual foi a taxa de churn por região no último trimestre? | 45 | 1468 |
| `sql_example:ex21` | Qual foi a taxa de churn de vendedores por região no último trimestre? | 50 | 1684 |
| `sql_example:ex22` | Qual a margem de contribuição por categoria? | 47 | 366 |
