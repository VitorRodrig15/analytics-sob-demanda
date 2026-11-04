# A1 - Perfil dos dados brutos (Olist)

Fonte: `data/raw/olist/` - 9 arquivos CSV.

## 1. Visao geral

| tabela               |   linhas |   colunas |   linhas duplicadas | chave                        | chaves repetidas   |   memoria (MB) |
|:---------------------|---------:|----------:|--------------------:|:-----------------------------|:-------------------|---------------:|
| customers            |    99441 |         5 |                   0 | customer_id                  | 0                  |           32.5 |
| geolocation          |  1000163 |         5 |              261831 | -                            | -                  |          182.6 |
| orders               |    99441 |         8 |                   0 | order_id                     | 0                  |           25.9 |
| order_items          |   112650 |         7 |                   0 | order_id, order_item_id      | 0                  |           31   |
| order_payments       |   103886 |         5 |                   0 | order_id, payment_sequential | 0                  |           17   |
| order_reviews        |    99224 |         7 |                   0 | review_id                    | 814                |           29.1 |
| products             |    32951 |         9 |                   0 | product_id                   | 0                  |            6.6 |
| sellers              |     3095 |         4 |                   0 | seller_id                    | 0                  |            0.8 |
| category_translation |       71 |         2 |                   0 | product_category_name        | 0                  |            0   |

## 2. Integridade entre tabelas

Registros da tabela filha cujo valor nao existe na tabela pai.

| ligacao                                                                       |   registros |   sem correspondencia |   % sem correspondencia | exemplos                                                |
|:------------------------------------------------------------------------------|------------:|----------------------:|------------------------:|:--------------------------------------------------------|
| orders.customer_id -> customers.customer_id                                   |       99441 |                     0 |                    0    |                                                         |
| order_items.order_id -> orders.order_id                                       |      112650 |                     0 |                    0    |                                                         |
| order_items.product_id -> products.product_id                                 |      112650 |                     0 |                    0    |                                                         |
| order_items.seller_id -> sellers.seller_id                                    |      112650 |                     0 |                    0    |                                                         |
| order_payments.order_id -> orders.order_id                                    |      103886 |                     0 |                    0    |                                                         |
| order_reviews.order_id -> orders.order_id                                     |       99224 |                     0 |                    0    |                                                         |
| products.product_category_name -> category_translation.product_category_name  |       32341 |                    13 |                    0.04 | pc_gamer, portateis_cozinha_e_preparadores_de_alimentos |
| customers.customer_zip_code_prefix -> geolocation.geolocation_zip_code_prefix |       99441 |                   278 |                    0.28 | 72300, 11547, 64605                                     |
| sellers.seller_zip_code_prefix -> geolocation.geolocation_zip_code_prefix     |        3095 |                     7 |                    0.23 | 82040, 91901, 72580                                     |

## 3. Periodo coberto pelas datas

| coluna                                | inicio              | fim                 |   nulos |
|:--------------------------------------|:--------------------|:--------------------|--------:|
| orders.order_purchase_timestamp       | 2016-09-04 21:15:19 | 2018-10-17 17:30:18 |       0 |
| orders.order_approved_at              | 2016-09-15 12:16:38 | 2018-09-03 17:40:06 |     160 |
| orders.order_delivered_carrier_date   | 2016-10-08 10:34:01 | 2018-09-11 19:48:28 |    1783 |
| orders.order_delivered_customer_date  | 2016-10-11 13:46:32 | 2018-10-17 13:22:46 |    2965 |
| orders.order_estimated_delivery_date  | 2016-09-30 00:00:00 | 2018-11-12 00:00:00 |       0 |
| order_items.shipping_limit_date       | 2016-09-19 00:15:34 | 2020-04-09 22:35:08 |       0 |
| order_reviews.review_creation_date    | 2016-10-02 00:00:00 | 2018-08-31 00:00:00 |       0 |
| order_reviews.review_answer_timestamp | 2016-10-07 18:32:28 | 2018-10-29 12:27:35 |       0 |

## 4. Distribuicoes de colunas-chave

### orders.order_status

| order_status   |   qtd |     % |
|:---------------|------:|------:|
| delivered      | 96478 | 97.02 |
| shipped        |  1107 |  1.11 |
| canceled       |   625 |  0.63 |
| unavailable    |   609 |  0.61 |
| invoiced       |   314 |  0.32 |
| processing     |   301 |  0.3  |
| created        |     5 |  0.01 |
| approved       |     2 |  0    |

### order_payments.payment_type

| payment_type   |   qtd |     % |
|:---------------|------:|------:|
| credit_card    | 76795 | 73.92 |
| boleto         | 19784 | 19.04 |
| voucher        |  5775 |  5.56 |
| debit_card     |  1529 |  1.47 |
| not_defined    |     3 |  0    |

### order_reviews.review_score

|   review_score |   qtd |     % |
|---------------:|------:|------:|
|              5 | 57328 | 57.78 |
|              4 | 19142 | 19.29 |
|              1 | 11424 | 11.51 |
|              3 |  8179 |  8.24 |
|              2 |  3151 |  3.18 |

### customers.customer_state

| customer_state   |   qtd |     % |
|:-----------------|------:|------:|
| SP               | 41746 | 41.98 |
| RJ               | 12852 | 12.92 |
| MG               | 11635 | 11.7  |
| RS               |  5466 |  5.5  |
| PR               |  5045 |  5.07 |
| SC               |  3637 |  3.66 |
| BA               |  3380 |  3.4  |
| DF               |  2140 |  2.15 |
| ES               |  2033 |  2.04 |
| GO               |  2020 |  2.03 |
| PE               |  1652 |  1.66 |
| CE               |  1336 |  1.34 |
| PA               |   975 |  0.98 |
| MT               |   907 |  0.91 |
| MA               |   747 |  0.75 |
| MS               |   715 |  0.72 |
| PB               |   536 |  0.54 |
| PI               |   495 |  0.5  |
| RN               |   485 |  0.49 |
| AL               |   413 |  0.42 |
| SE               |   350 |  0.35 |
| TO               |   280 |  0.28 |
| RO               |   253 |  0.25 |
| AM               |   148 |  0.15 |
| AC               |    81 |  0.08 |
| AP               |    68 |  0.07 |
| RR               |    46 |  0.05 |

## 5. Perfil por coluna

### customers

| coluna                   | tipo   |   nulos |   % nulos |   valores distintos | faixa / exemplo                       |
|:-------------------------|:-------|--------:|----------:|--------------------:|:--------------------------------------|
| customer_id              | str    |       0 |         0 |               99441 | ex.: 06b8999e2fba1a1fbc88172c00ba8bc7 |
| customer_unique_id       | str    |       0 |         0 |               96096 | ex.: 861eff4711a542e4b93843c6dd7febb0 |
| customer_zip_code_prefix | str    |       0 |         0 |               14994 | ex.: 14409                            |
| customer_city            | str    |       0 |         0 |                4119 | ex.: franca                           |
| customer_state           | str    |       0 |         0 |                  27 | ex.: SP                               |

### geolocation

| coluna                      | tipo    |   nulos |   % nulos |   valores distintos | faixa / exemplo                           |
|:----------------------------|:--------|--------:|----------:|--------------------:|:------------------------------------------|
| geolocation_zip_code_prefix | str     |       0 |         0 |               19015 | ex.: 01037                                |
| geolocation_lat             | float64 |       0 |         0 |              717372 | -36.6053744107061 -> 45.06593318269697    |
| geolocation_lng             | float64 |       0 |         0 |              717615 | -101.46676644931476 -> 121.10539381057764 |
| geolocation_city            | str     |       0 |         0 |                8011 | ex.: sao paulo                            |
| geolocation_state           | str     |       0 |         0 |                  27 | ex.: SP                                   |

### orders

| coluna                        | tipo           |   nulos |   % nulos |   valores distintos | faixa / exemplo                            |
|:------------------------------|:---------------|--------:|----------:|--------------------:|:-------------------------------------------|
| order_id                      | str            |       0 |      0    |               99441 | ex.: e481f51cbdc54678b7cc49136f2d6af7      |
| customer_id                   | str            |       0 |      0    |               99441 | ex.: 9ef432eb6251297304e76186b10a928d      |
| order_status                  | str            |       0 |      0    |                   8 | ex.: delivered                             |
| order_purchase_timestamp      | datetime64[us] |       0 |      0    |               98875 | 2016-09-04 21:15:19 -> 2018-10-17 17:30:18 |
| order_approved_at             | datetime64[us] |     160 |      0.16 |               90733 | 2016-09-15 12:16:38 -> 2018-09-03 17:40:06 |
| order_delivered_carrier_date  | datetime64[us] |    1783 |      1.79 |               81018 | 2016-10-08 10:34:01 -> 2018-09-11 19:48:28 |
| order_delivered_customer_date | datetime64[us] |    2965 |      2.98 |               95664 | 2016-10-11 13:46:32 -> 2018-10-17 13:22:46 |
| order_estimated_delivery_date | datetime64[us] |       0 |      0    |                 459 | 2016-09-30 00:00:00 -> 2018-11-12 00:00:00 |

### order_items

| coluna              | tipo           |   nulos |   % nulos |   valores distintos | faixa / exemplo                            |
|:--------------------|:---------------|--------:|----------:|--------------------:|:-------------------------------------------|
| order_id            | str            |       0 |         0 |               98666 | ex.: 00010242fe8c5a6d1ba2dd792cb16214      |
| order_item_id       | int64          |       0 |         0 |                  21 | 1 -> 21                                    |
| product_id          | str            |       0 |         0 |               32951 | ex.: 4244733e06e7ecb4970a6e2683c13e61      |
| seller_id           | str            |       0 |         0 |                3095 | ex.: 48436dade18ac8b2bce089ec2a041202      |
| shipping_limit_date | datetime64[us] |       0 |         0 |               93318 | 2016-09-19 00:15:34 -> 2020-04-09 22:35:08 |
| price               | float64        |       0 |         0 |                5968 | 0.85 -> 6735.0                             |
| freight_value       | float64        |       0 |         0 |                6999 | 0.0 -> 409.68                              |

### order_payments

| coluna               | tipo    |   nulos |   % nulos |   valores distintos | faixa / exemplo                       |
|:---------------------|:--------|--------:|----------:|--------------------:|:--------------------------------------|
| order_id             | str     |       0 |         0 |               99440 | ex.: b81ef226f3fe1789b1e8b2acac839d17 |
| payment_sequential   | int64   |       0 |         0 |                  29 | 1 -> 29                               |
| payment_type         | str     |       0 |         0 |                   5 | ex.: credit_card                      |
| payment_installments | int64   |       0 |         0 |                  24 | 0 -> 24                               |
| payment_value        | float64 |       0 |         0 |               29077 | 0.0 -> 13664.08                       |

### order_reviews

| coluna                  | tipo           |   nulos |   % nulos |   valores distintos | faixa / exemplo                            |
|:------------------------|:---------------|--------:|----------:|--------------------:|:-------------------------------------------|
| review_id               | str            |       0 |      0    |               98410 | ex.: 7bc2406110b926393aa56f80a40eba40      |
| order_id                | str            |       0 |      0    |               98673 | ex.: 73fc7af87114b39712e6da79b0a377eb      |
| review_score            | int64          |       0 |      0    |                   5 | 1 -> 5                                     |
| review_comment_title    | str            |   87656 |     88.34 |                4527 | ex.: recomendo                             |
| review_comment_message  | str            |   58247 |     58.7  |               36159 | ex.: Recebi bem antes do prazo estipulado. |
| review_creation_date    | datetime64[us] |       0 |      0    |                 636 | 2016-10-02 00:00:00 -> 2018-08-31 00:00:00 |
| review_answer_timestamp | datetime64[us] |       0 |      0    |               98248 | 2016-10-07 18:32:28 -> 2018-10-29 12:27:35 |

### products

| coluna                     | tipo    |   nulos |   % nulos |   valores distintos | faixa / exemplo                       |
|:---------------------------|:--------|--------:|----------:|--------------------:|:--------------------------------------|
| product_id                 | str     |       0 |      0    |               32951 | ex.: 1e9e8ef04dbcff4541ed26657ea517e5 |
| product_category_name      | str     |     610 |      1.85 |                  73 | ex.: perfumaria                       |
| product_name_lenght        | float64 |     610 |      1.85 |                  66 | 5.0 -> 76.0                           |
| product_description_lenght | float64 |     610 |      1.85 |                2960 | 4.0 -> 3992.0                         |
| product_photos_qty         | float64 |     610 |      1.85 |                  19 | 1.0 -> 20.0                           |
| product_weight_g           | float64 |       2 |      0.01 |                2204 | 0.0 -> 40425.0                        |
| product_length_cm          | float64 |       2 |      0.01 |                  99 | 7.0 -> 105.0                          |
| product_height_cm          | float64 |       2 |      0.01 |                 102 | 2.0 -> 105.0                          |
| product_width_cm           | float64 |       2 |      0.01 |                  95 | 6.0 -> 118.0                          |

### sellers

| coluna                 | tipo   |   nulos |   % nulos |   valores distintos | faixa / exemplo                       |
|:-----------------------|:-------|--------:|----------:|--------------------:|:--------------------------------------|
| seller_id              | str    |       0 |         0 |                3095 | ex.: 3442f8959a84dea7ee197c632cb2df15 |
| seller_zip_code_prefix | str    |       0 |         0 |                2246 | ex.: 13023                            |
| seller_city            | str    |       0 |         0 |                 611 | ex.: campinas                         |
| seller_state           | str    |       0 |         0 |                  23 | ex.: SP                               |

### category_translation

| coluna                        | tipo   |   nulos |   % nulos |   valores distintos | faixa / exemplo    |
|:------------------------------|:-------|--------:|----------:|--------------------:|:-------------------|
| product_category_name         | str    |       0 |         0 |                  71 | ex.: beleza_saude  |
| product_category_name_english | str    |       0 |         0 |                  71 | ex.: health_beauty |
