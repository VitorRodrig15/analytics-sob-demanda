-- =============================================================================
-- Entregavel 2.2 (E2) - Modelagem do schema dw (passo A2)
--
-- Modelei estas 8 tabelas pensando sempre na mesma pergunta: quem vai
-- escrever SQL em cima disso e um agente de IA, entao quanto mais claro
-- o modelo, menos chance de erro. Por isso tipos corretos (data como data,
-- dinheiro como NUMERIC, nunca float), chaves estrangeiras explicitas, uma
-- coluna de regiao (o problema de negocio pergunta "por regiao" e o Olist
-- so vem com estado) e a traducao de categoria incorporada direto em
-- products, pra economizar um JOIN inteiro do agente.
--
-- Executar como script no DBeaver (Alt + X), nunca comando a comando com
-- Ctrl+Enter - a ordem das tabelas importa, porque cada FK depende da
-- tabela anterior ja existir. ATENCAO: apaga os dados carregados.
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS dw;

-- Recria do zero (ordem inversa das dependencias)
DROP TABLE IF EXISTS dw.order_reviews, dw.order_payments, dw.order_items,
                     dw.orders, dw.products, dw.sellers, dw.customers,
                     dw.geolocation CASCADE;

-- -----------------------------------------------------------------------------
-- Geolocalizacao: 1 linha por CEP (agregada no load_dw.py a partir de 1
-- milhao de linhas do CSV bruto - a maioria nao e duplicata de verdade, sao
-- pontos de GPS distintos dentro do mesmo CEP, que cobre uma regiao inteira)
-- -----------------------------------------------------------------------------
CREATE TABLE dw.geolocation (
    geolocation_zip_code_prefix CHAR(5)          PRIMARY KEY,
    geolocation_lat             DOUBLE PRECISION,
    geolocation_lng             DOUBLE PRECISION,
    geolocation_city            TEXT,
    geolocation_state           CHAR(2)
);

-- -----------------------------------------------------------------------------
-- Clientes: 1 linha por cliente NO PEDIDO (customer_id muda a cada pedido).
-- O cliente real e identificado por customer_unique_id.
-- -----------------------------------------------------------------------------
CREATE TABLE dw.customers (
    customer_id              TEXT    PRIMARY KEY,
    customer_unique_id       TEXT    NOT NULL,
    customer_zip_code_prefix CHAR(5) NOT NULL,
    customer_city            TEXT,
    customer_state           CHAR(2) NOT NULL,
    customer_region          TEXT    NOT NULL
        CHECK (customer_region IN ('Norte','Nordeste','Centro-Oeste','Sudeste','Sul'))
);

-- -----------------------------------------------------------------------------
-- Vendedores
-- -----------------------------------------------------------------------------
CREATE TABLE dw.sellers (
    seller_id              TEXT    PRIMARY KEY,
    seller_zip_code_prefix CHAR(5) NOT NULL,
    seller_city            TEXT,
    seller_state           CHAR(2) NOT NULL,
    seller_region          TEXT    NOT NULL
        CHECK (seller_region IN ('Norte','Nordeste','Centro-Oeste','Sudeste','Sul'))
);

-- -----------------------------------------------------------------------------
-- Produtos (traducao da categoria incorporada; "lenght" corrigido para "length")
-- -----------------------------------------------------------------------------
CREATE TABLE dw.products (
    product_id                    TEXT PRIMARY KEY,
    product_category_name         TEXT NOT NULL,   -- 'sem_categoria' quando vazio
    product_category_name_english TEXT NOT NULL,
    product_name_length           SMALLINT,
    product_description_length    INTEGER,
    product_photos_qty            SMALLINT,
    product_weight_g              INTEGER,
    product_length_cm             SMALLINT,
    product_height_cm             SMALLINT,
    product_width_cm              SMALLINT
);

-- -----------------------------------------------------------------------------
-- Pedidos. order_estimated_delivery_date e usada pelo dicionario (B1) pra
-- calcular a taxa de entregas no prazo; order_purchase_timestamp e a coluna
-- de referencia pra qualquer filtro de periodo no projeto todo.
-- -----------------------------------------------------------------------------
CREATE TABLE dw.orders (
    order_id                      TEXT      PRIMARY KEY,
    customer_id                   TEXT      NOT NULL REFERENCES dw.customers (customer_id),
    order_status                  TEXT      NOT NULL
        CHECK (order_status IN ('created','approved','invoiced','processing',
                                'shipped','delivered','canceled','unavailable')),
    order_purchase_timestamp      TIMESTAMP NOT NULL,
    order_approved_at             TIMESTAMP,
    order_delivered_carrier_date  TIMESTAMP,
    order_delivered_customer_date TIMESTAMP,
    order_estimated_delivery_date TIMESTAMP NOT NULL
);

-- -----------------------------------------------------------------------------
-- Itens do pedido (1 linha por item; um pedido pode ter varios)
-- -----------------------------------------------------------------------------
CREATE TABLE dw.order_items (
    order_id            TEXT          NOT NULL REFERENCES dw.orders (order_id),
    order_item_id       SMALLINT      NOT NULL,
    product_id          TEXT          NOT NULL REFERENCES dw.products (product_id),
    seller_id           TEXT          NOT NULL REFERENCES dw.sellers (seller_id),
    shipping_limit_date TIMESTAMP     NOT NULL,
    price               NUMERIC(10,2) NOT NULL CHECK (price >= 0),
    freight_value       NUMERIC(10,2) NOT NULL CHECK (freight_value >= 0),
    PRIMARY KEY (order_id, order_item_id)
);

-- -----------------------------------------------------------------------------
-- Pagamentos (um pedido pode ter varios: cartao + voucher, por exemplo)
-- -----------------------------------------------------------------------------
CREATE TABLE dw.order_payments (
    order_id             TEXT          NOT NULL REFERENCES dw.orders (order_id),
    payment_sequential   SMALLINT      NOT NULL,
    payment_type         TEXT          NOT NULL,
    payment_installments SMALLINT      NOT NULL,
    payment_value        NUMERIC(10,2) NOT NULL CHECK (payment_value >= 0),
    PRIMARY KEY (order_id, payment_sequential)
);

-- -----------------------------------------------------------------------------
-- Avaliacoes (review_id repete em 814 casos -> chave composta)
-- -----------------------------------------------------------------------------
CREATE TABLE dw.order_reviews (
    review_id               TEXT      NOT NULL,
    order_id                TEXT      NOT NULL REFERENCES dw.orders (order_id),
    review_score            SMALLINT  NOT NULL CHECK (review_score BETWEEN 1 AND 5),
    review_comment_title    TEXT,
    review_comment_message  TEXT,
    review_creation_date    TIMESTAMP NOT NULL,
    review_answer_timestamp TIMESTAMP,
    PRIMARY KEY (review_id, order_id)
);

-- -----------------------------------------------------------------------------
-- Indices para JOINs e filtros por periodo - essenciais pra manter a meta
-- de resposta em menos de 2 minutos que defini la na E1, mesmo com as
-- 569.703 linhas que o load_dw.py carrega.
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_customers_unique_id   ON dw.customers (customer_unique_id);
CREATE INDEX IF NOT EXISTS idx_customers_state       ON dw.customers (customer_state);
CREATE INDEX IF NOT EXISTS idx_orders_customer       ON dw.orders (customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_purchase_ts    ON dw.orders (order_purchase_timestamp);
CREATE INDEX IF NOT EXISTS idx_orders_status         ON dw.orders (order_status);
CREATE INDEX IF NOT EXISTS idx_order_items_product   ON dw.order_items (product_id);
CREATE INDEX IF NOT EXISTS idx_order_items_seller    ON dw.order_items (seller_id);
CREATE INDEX IF NOT EXISTS idx_order_reviews_order   ON dw.order_reviews (order_id);
CREATE INDEX IF NOT EXISTS idx_products_category     ON dw.products (product_category_name);

-- -----------------------------------------------------------------------------
-- Descricoes de cada tabela: aparecem no DBeaver pra quem for explorar o
-- banco, e foram a base que usei pra escrever o knowledge/tabelas.md (B1).
-- -----------------------------------------------------------------------------
COMMENT ON SCHEMA dw IS 'Dados de negocio do marketplace (Olist 2016-2018). Dados confiaveis ate 2018-08.';
COMMENT ON TABLE dw.geolocation    IS '1 linha por prefixo de CEP, com latitude/longitude medias.';
COMMENT ON TABLE dw.customers      IS 'Cliente por pedido. Para contar clientes reais use customer_unique_id.';
COMMENT ON TABLE dw.sellers        IS 'Vendedores do marketplace.';
COMMENT ON TABLE dw.products       IS 'Catalogo de produtos com categoria em portugues e ingles.';
COMMENT ON TABLE dw.orders         IS 'Pedidos. Para metricas de venda e entrega filtre order_status = ''delivered''.';
COMMENT ON TABLE dw.order_items    IS 'Itens dos pedidos. Receita = SUM(price); frete = SUM(freight_value).';
COMMENT ON TABLE dw.order_payments IS 'Pagamentos dos pedidos; um pedido pode ter varios pagamentos.';
COMMENT ON TABLE dw.order_reviews  IS 'Avaliacoes dos clientes (nota de 1 a 5).';
