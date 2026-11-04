# Tabelas do Data Warehouse (schema dw)

Descrição das tabelas disponíveis para consulta. Todas ficam no schema `dw` e devem ser
referenciadas com o prefixo (`dw.orders`). Dados do marketplace de 2016 a 2018.

## dw.orders — pedidos

- **Uma linha =** um pedido.
- **Chave:** `order_id`
- **Liga com:** `dw.customers` por `customer_id`; é a tabela pai de `dw.order_items`, `dw.order_payments` e `dw.order_reviews` (por `order_id`).
- **Volume:** 99.441 pedidos.
- **Colunas:**
  - `order_id` (text): identificador do pedido.
  - `customer_id` (text): cliente do pedido (muda a cada pedido; ver `customer_unique_id`).
  - `order_status` (text): created, approved, invoiced, processing, shipped, delivered (97%), canceled, unavailable.
  - `order_purchase_timestamp` (timestamp): data e hora da compra. **Data de referência para períodos.**
  - `order_approved_at` (timestamp): aprovação do pagamento.
  - `order_delivered_carrier_date` (timestamp): entrega à transportadora.
  - `order_delivered_customer_date` (timestamp): entrega ao cliente; nula em pedidos não entregues.
  - `order_estimated_delivery_date` (timestamp): data prometida ao cliente (sempre meia-noite).
- **Cuidados:** filtrar `order_status = 'delivered'` em métricas de venda e entrega.

## dw.order_items — itens dos pedidos

- **Uma linha =** um item de um pedido (um pedido com 3 unidades tem 3 linhas).
- **Chave:** `order_id` + `order_item_id`
- **Liga com:** `dw.orders` (order_id), `dw.products` (product_id), `dw.sellers` (seller_id).
- **Volume:** 112.650 itens.
- **Colunas:**
  - `order_id` (text): pedido.
  - `order_item_id` (smallint): sequência do item dentro do pedido (1, 2, 3…).
  - `product_id` (text): produto vendido.
  - `seller_id` (text): vendedor que vendeu o item.
  - `shipping_limit_date` (timestamp): prazo para o vendedor despachar.
  - `price` (numeric R$): preço do item. **Base da receita.**
  - `freight_value` (numeric R$): frete do item.
- **Cuidados:** é a única tabela com valores de venda e o único caminho entre pedido, produto e vendedor. Um pedido pode ter itens de vendedores diferentes.

## dw.order_payments — pagamentos

- **Uma linha =** um pagamento de um pedido (ex.: cartão + voucher = 2 linhas).
- **Chave:** `order_id` + `payment_sequential`
- **Liga com:** `dw.orders` por `order_id`.
- **Volume:** 103.886 pagamentos.
- **Colunas:**
  - `order_id` (text): pedido.
  - `payment_sequential` (smallint): ordem do pagamento no pedido (1 = principal).
  - `payment_type` (text): credit_card, boleto, voucher, debit_card, not_defined.
  - `payment_installments` (smallint): número de parcelas.
  - `payment_value` (numeric R$): valor pago (inclui frete e juros).
- **Cuidados:** não juntar com `dw.order_items` diretamente (multiplica linhas). Para "forma de pagamento do pedido", use `payment_sequential = 1`.

## dw.order_reviews — avaliações

- **Uma linha =** uma avaliação de um pedido.
- **Chave:** `review_id` + `order_id` (o mesmo `review_id` pode aparecer em pedidos diferentes).
- **Liga com:** `dw.orders` por `order_id`.
- **Volume:** 99.224 avaliações.
- **Colunas:**
  - `review_id` (text): identificador da avaliação.
  - `order_id` (text): pedido avaliado.
  - `review_score` (smallint): nota de 1 a 5.
  - `review_comment_title` (text): título do comentário (88% vazio).
  - `review_comment_message` (text): comentário do cliente (59% vazio).
  - `review_creation_date` (timestamp): envio da pesquisa ao cliente.
  - `review_answer_timestamp` (timestamp): resposta do cliente.
- **Cuidados:** alguns pedidos têm mais de uma avaliação; agregue por pedido antes de juntar com itens.

## dw.customers — clientes

- **Uma linha =** o cliente **de um pedido** (99.441 linhas, mas 96.096 pessoas distintas).
- **Chave:** `customer_id`
- **Liga com:** `dw.orders` por `customer_id`; `dw.geolocation` por CEP (LEFT JOIN, sem chave estrangeira).
- **Colunas:**
  - `customer_id` (text): identificador por pedido.
  - `customer_unique_id` (text): **identificador real da pessoa**. Use para contar clientes.
  - `customer_zip_code_prefix` (char 5): prefixo do CEP.
  - `customer_city` (text): cidade, minúscula e sem acento (ex.: `sao paulo`).
  - `customer_state` (char 2): UF (ex.: SP).
  - `customer_region` (text): Norte, Nordeste, Centro-Oeste, Sudeste ou Sul.
- **Cuidados:** cidades estão sem acento e em minúsculas; compare com `customer_city = 'sao paulo'`.

## dw.sellers — vendedores

- **Uma linha =** um vendedor do marketplace.
- **Chave:** `seller_id`
- **Liga com:** `dw.order_items` por `seller_id`; `dw.geolocation` por CEP (LEFT JOIN).
- **Volume:** 3.095 vendedores.
- **Colunas:**
  - `seller_id` (text): identificador do vendedor.
  - `seller_zip_code_prefix` (char 5): prefixo do CEP.
  - `seller_city` (text): cidade, minúscula e sem acento.
  - `seller_state` (char 2): UF.
  - `seller_region` (text): região do vendedor.
- **Cuidados:** vendedores não têm nome; identifique-os pelo `seller_id` e pela cidade/UF.

## dw.products — produtos

- **Uma linha =** um produto do catálogo.
- **Chave:** `product_id`
- **Liga com:** `dw.order_items` por `product_id`.
- **Volume:** 32.951 produtos em 74 categorias.
- **Colunas:**
  - `product_id` (text): identificador do produto.
  - `product_category_name` (text): categoria em português (ex.: `cama_mesa_banho`, `beleza_saude`); `sem_categoria` quando ausente.
  - `product_category_name_english` (text): categoria em inglês.
  - `product_name_length` (smallint): quantidade de caracteres do nome.
  - `product_description_length` (integer): quantidade de caracteres da descrição.
  - `product_photos_qty` (smallint): quantidade de fotos no anúncio.
  - `product_weight_g` (integer): peso em gramas.
  - `product_length_cm`, `product_height_cm`, `product_width_cm` (smallint): dimensões em cm.
- **Cuidados:** produtos não têm nome nem preço de tabela; o preço praticado está em `dw.order_items.price`. Nomes de categoria usam `_` no lugar de espaço.

## dw.geolocation — geolocalização por CEP

- **Uma linha =** um prefixo de CEP (19.015 CEPs).
- **Chave:** `geolocation_zip_code_prefix`
- **Liga com:** `dw.customers.customer_zip_code_prefix` e `dw.sellers.seller_zip_code_prefix`, **sempre com LEFT JOIN**.
- **Colunas:**
  - `geolocation_zip_code_prefix` (char 5): prefixo do CEP.
  - `geolocation_lat`, `geolocation_lng` (double): coordenadas médias do CEP (nulas em 5 CEPs).
  - `geolocation_city` (text): cidade mais frequente do CEP.
  - `geolocation_state` (char 2): UF.
- **Cuidados:** use apenas para mapas ou distância; estado e região já estão em customers e sellers.
