# Regras de Negócio — Vortex Marketplace

Regras que o assistente deve aplicar em toda consulta, além das definições de métricas.

## Período confiável dos dados

Os pedidos vão de set/2016 a out/2018, mas as pontas estão incompletas: 2016 tem cerca de 330 pedidos e set–out/2018 têm apenas 20. **Os dados confiáveis vão de jan/2017 a ago/2018.** Sempre limite as consultas com `order_purchase_timestamp < '2018-09-01'`. Ao analisar 2016, avise que o volume é pequeno e não representativo.

## Datas relativas ("último mês", "último trimestre")

A data de referência ("hoje") dos dados é **2018-08-31**. Nunca use `CURRENT_DATE` ou `NOW()`: elas apontam para a data real e retornariam vazio.

| Expressão do usuário | Período |
|---|---|
| último mês / mês passado | 2018-08-01 a 2018-08-31 |
| último trimestre / últimos 3 meses | 2018-06-01 a 2018-08-31 |
| último semestre / últimos 6 meses | 2018-03-01 a 2018-08-31 |
| este ano / ano atual | 2018-01-01 a 2018-08-31 |
| ano passado | 2017-01-01 a 2017-12-31 |
| últimos 12 meses | 2017-09-01 a 2018-08-31 |

Use intervalos fechados no início e abertos no fim: `>= '2018-06-01' AND < '2018-09-01'`.

## Comparação entre anos

Para comparar 2018 com 2017, use o **mesmo intervalo de meses** (jan–ago de cada ano). Comparar 2018 parcial com 2017 completo mostraria uma queda falsa.

## Status do pedido

- Métricas de venda, entrega, clientes e avaliação: somente `order_status = 'delivered'`.
- Taxa de cancelamento: todos os pedidos no denominador; `canceled` e `unavailable` contam como cancelados.
- Status possíveis: created, approved, invoiced, processing, shipped, delivered, canceled, unavailable.

## Data de referência do pedido

Para atribuir um pedido a um período, use **`order_purchase_timestamp`** (data da compra), inclusive em métricas de entrega e avaliação. Não use a data de entrega nem a da avaliação para filtrar o período.

## Identificação do cliente

O cliente real é **`customer_unique_id`**. O `customer_id` é gerado a cada pedido: contar `customer_id` equivale a contar pedidos. Use `customer_unique_id` para clientes únicos, recompra e churn.

## Receita, frete e pagamentos

- Receita = `SUM(order_items.price)`, sem frete.
- Faturamento com frete / GMV total = `SUM(price + freight_value)`.
- `order_payments.payment_value` é o valor pago pelo cliente (inclui frete, juros de parcelamento e vouchers). Use apenas para perguntas sobre **pagamento** (forma de pagamento, parcelas, valor pago).

## Multiplicação de linhas em JOINs

Um pedido pode ter vários itens, vários pagamentos e mais de uma avaliação. **Nunca junte `order_items` com `order_payments` ou com `order_reviews` diretamente na mesma consulta**: as linhas se multiplicam e as somas ficam infladas. Agregue cada tabela por `order_id` em uma CTE e depois junte os resultados.

## Região

A região vem das colunas `customer_region` (cliente) e `seller_region` (vendedor), derivadas do estado:

- **Norte:** AC, AP, AM, PA, RO, RR, TO
- **Nordeste:** AL, BA, CE, MA, PB, PE, PI, RN, SE
- **Centro-Oeste:** DF, GO, MT, MS
- **Sudeste:** ES, MG, RJ, SP
- **Sul:** PR, RS, SC

"Vendas por região" usa a região do **cliente**, salvo se o usuário falar em vendedor.

## Geolocalização

`dw.geolocation` tem uma linha por prefixo de CEP e se liga a clientes e vendedores pelo CEP, **sem chave estrangeira**. Use sempre **LEFT JOIN**: 0,3% dos CEPs não existem na tabela e 5 CEPs não têm coordenadas. Só use a tabela para latitude/longitude; estado e região já estão em customers e sellers.

## Categorias de produto

Responda com `product_category_name` (português). A coluna `product_category_name_english` existe para tradução. Produtos sem categoria aparecem como `sem_categoria` e devem ser mantidos nas somas, mas podem ser omitidos de rankings se o usuário pedir.

## Métricas indisponíveis

O dataset não tem custo de produto, comissão, despesas, estoque, marketing nem metas. Perguntas sobre **margem, lucro, CMV, ROI, CAC ou estoque** não podem ser respondidas: explique o motivo e ofereça uma métrica disponível. Nunca estime valores ausentes.

## Segurança e boas práticas de SQL

- Somente `SELECT` (ou `WITH ... SELECT`) no schema `dw`. Nunca INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE ou GRANT.
- Não use `SELECT *`: liste as colunas necessárias.
- Listagens e rankings devem ter `LIMIT` (padrão 10; máximo 100).
- Valores monetários em reais (R$), arredondados com `ROUND(valor, 2)`.
- Percentuais multiplicados por 100 e arredondados com 2 casas.
