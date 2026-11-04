# D1 - Validação da ingestão (entregável 2.5)

**18 de 18 verificações aprovadas.**

## Resumo das verificações

| Verificação | Resultado | Detalhe |
|---|---|---|
| PostgreSQL + pgvector | ✅ | PostgreSQL 16.15 (Debian 16.15-1.pgdg12+2), pgvector 0.8.7 |
| dw.geolocation | ✅ | 19015 linhas (esperado 19015) |
| dw.customers | ✅ | 99441 linhas (esperado 99441) |
| dw.sellers | ✅ | 3095 linhas (esperado 3095) |
| dw.products | ✅ | 32951 linhas (esperado 32951) |
| dw.orders | ✅ | 99441 linhas (esperado 99441) |
| dw.order_items | ✅ | 112650 linhas (esperado 112650) |
| dw.order_payments | ✅ | 103886 linhas (esperado 103886) |
| dw.order_reviews | ✅ | 99224 linhas (esperado 99224) |
| chunks business_rule | ✅ | 13 no banco (esperado 13) |
| chunks metric | ✅ | 18 no banco (esperado 18) |
| chunks sql_example | ✅ | 22 no banco (esperado 22) |
| chunks table_schema | ✅ | 8 no banco (esperado 8) |
| embeddings preenchidos | ✅ | 61 de 61 |
| dimensão dos vetores | ✅ | [1024] |
| modelo único | ✅ | ['nvidia/nemotron-3.5-embed-1b'] |
| índice HNSW | ✅ | idx_documents_embedding |
| busca: acerto entre os 3 primeiros | ✅ | 12/12 (100%); 1º lugar: 10/12 |

## Dados de negócio: CSV x banco

| Tabela | Linhas no CSV | Esperado no banco | No banco |
|---|---|---|---|
| dw.geolocation | 1.000.163 | 19.015 | 19.015 |
| dw.customers | 99.441 | 99.441 | 99.441 |
| dw.sellers | 3.095 | 3.095 | 3.095 |
| dw.products | 32.951 | 32.951 | 32.951 |
| dw.orders | 99.441 | 99.441 | 99.441 |
| dw.order_items | 112.650 | 112.650 | 112.650 |
| dw.order_payments | 103.886 | 103.886 | 103.886 |
| dw.order_reviews | 99.224 | 99.224 | 99.224 |

`geolocation` é agregada para 1 linha por CEP (decisão do A3); as demais devem bater 1 para 1.

## Amostra de embeddings (5 primeiros de 1024 valores)

| Chunk | Início do vetor |
|---|---|
| `business_rule:status-do-pedido` | `[0.1772238,-0.0002144,-0.0734288,-0.0046602,0.0364526,-0.0173646,-0.0279012,-0.0...` |
| `metric:ticket-medio` | `[0.1183302,0.0344951,-0.0418746,0.0033331,0.0195215,-0.0359967,-0.0214736,-0.034...` |
| `sql_example:ex21` | `[0.147514,0.0925478,-0.016671,-0.0187588,0.0136563,-0.0130065,0.0144553,0.006812...` |

## Busca de teste (top 3 por similaridade de cosseno)

SQL usado na busca (o vetor da pergunta é gerado com o mesmo modelo, tipo *query*):

```sql
SELECT id, doc_type, title, 1 - (embedding <=> :vetor_da_pergunta::vector) AS similaridade
    FROM rag.documents
    ORDER BY embedding <=> :vetor_da_pergunta::vector
    LIMIT 3
```

**Acerto entre os 3 primeiros: 12/12** · **Acerto em 1º lugar: 10/12**

### Qual o valor médio gasto em cada compra?

✅ acerto na posição 1

| # | Chunk | Similaridade |
|---|---|---|
| 1 | `metric:ticket-medio` | 0.279 |
| 2 | `metric:itens-por-pedido` | 0.248 |
| 3 | `metric:receita-por-vendedor` | 0.214 |

### Quantos lojistas pararam de vender em cada região?

✅ acerto na posição 2

| # | Chunk | Similaridade |
|---|---|---|
| 1 | `business_rule:regiao` | 0.382 |
| 2 | `metric:churn-de-vendedores` | 0.317 |
| 3 | `table_schema:dw.sellers-vendedores` | 0.298 |

### As entregas estão chegando dentro do prazo prometido?

✅ acerto na posição 1

| # | Chunk | Similaridade |
|---|---|---|
| 1 | `metric:entregas-no-prazo` | 0.497 |
| 2 | `metric:tempo-medio-de-entrega` | 0.356 |
| 3 | `sql_example:ex09` | 0.348 |

### Qual o lucro que tivemos por categoria?

✅ acerto na posição 2

| # | Chunk | Similaridade |
|---|---|---|
| 1 | `business_rule:categorias-de-produto` | 0.374 |
| 2 | `sql_example:ex22` | 0.349 |
| 3 | `sql_example:ex16` | 0.343 |

### Como contar clientes sem repetir a mesma pessoa?

✅ acerto na posição 1

| # | Chunk | Similaridade |
|---|---|---|
| 1 | `metric:clientes-unicos` | 0.528 |
| 2 | `business_rule:identificacao-do-cliente` | 0.505 |
| 3 | `table_schema:dw.customers-clientes` | 0.454 |

### Quais informações existem sobre as formas de pagamento?

✅ acerto na posição 1

| # | Chunk | Similaridade |
|---|---|---|
| 1 | `table_schema:dw.order-payments-pagamentos` | 0.339 |
| 2 | `business_rule:receita-frete-e-pagamentos` | 0.274 |
| 3 | `sql_example:ex08` | 0.224 |

### Que período devo usar quando pedem o último trimestre?

✅ acerto na posição 1

| # | Chunk | Similaridade |
|---|---|---|
| 1 | `business_rule:datas-relativas-ultimo-mes-ultimo-trimestre` | 0.527 |
| 2 | `sql_example:ex04` | 0.336 |
| 3 | `business_rule:data-de-referencia-do-pedido` | 0.294 |

### Os clientes estão satisfeitos com as compras?

✅ acerto na posição 1

| # | Chunk | Similaridade |
|---|---|---|
| 1 | `metric:avaliacoes-positivas-e-negativas` | 0.307 |
| 2 | `business_rule:identificacao-do-cliente` | 0.307 |
| 3 | `metric:churn-de-clientes` | 0.288 |

### Quais tipos de produto mais faturam?

✅ acerto na posição 1

| # | Chunk | Similaridade |
|---|---|---|
| 1 | `metric:receita` | 0.244 |
| 2 | `metric:receita-por-vendedor` | 0.212 |
| 3 | `table_schema:dw.products-produtos` | 0.204 |

### Quanto o frete representa nas vendas do Norte?

✅ acerto na posição 1

| # | Chunk | Similaridade |
|---|---|---|
| 1 | `metric:percentual-do-frete-sobre-a-receita` | 0.373 |
| 2 | `business_rule:regiao` | 0.318 |
| 3 | `business_rule:receita-frete-e-pagamentos` | 0.303 |

### A consulta pode apagar ou alterar dados?

✅ acerto na posição 1

| # | Chunk | Similaridade |
|---|---|---|
| 1 | `business_rule:seguranca-e-boas-praticas-de-sql` | 0.303 |
| 2 | `business_rule:periodo-confiavel-dos-dados` | 0.279 |
| 3 | `business_rule:multiplicacao-de-linhas-em-joins` | 0.254 |

### Quantos pedidos foram cancelados este ano?

✅ acerto na posição 1

| # | Chunk | Similaridade |
|---|---|---|
| 1 | `metric:taxa-de-cancelamento` | 0.502 |
| 2 | `business_rule:status-do-pedido` | 0.388 |
| 3 | `metric:numero-de-pedidos` | 0.320 |
