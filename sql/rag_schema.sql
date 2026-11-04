-- =============================================================================
-- Entregavel 2.4 (E2) - Schema rag: chunks do dicionario + embeddings (passo C2)
--
-- Esse e o schema que guarda o CONHECIMENTO, separado do schema dw que
-- guarda os DADOS - mesma decisao de infraestrutura que tomei la na E1
-- (1.4 C): um banco so, dois schemas, pra nao misturar as duas coisas.
-- A dimensao do vetor (1024) foi escolhida depois que o modelo de embedding
-- que eu tinha planejado originalmente foi descontinuado pela NVIDIA no
-- meio da E2 - ver o embed_chunks.py pra entender essa historia completa.
-- Precisa bater com EMBEDDING_DIM do .env.
--
-- Idempotente de proposito: pode rodar varias vezes sem apagar dados que
-- ja existam, porque e o embed_chunks.py quem chama este script toda vez.
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS rag;

CREATE TABLE IF NOT EXISTS rag.documents (
    id              TEXT         PRIMARY KEY,          -- ex.: metric:ticket-medio
    doc_type        TEXT         NOT NULL
        CHECK (doc_type IN ('metric', 'business_rule', 'table_schema', 'sql_example')),
    source          TEXT         NOT NULL,             -- arquivo de origem em knowledge/
    title           TEXT         NOT NULL,
    search_text     TEXT         NOT NULL,             -- texto que virou embedding
    content         TEXT         NOT NULL,             -- texto entregue ao agente (com SQL)
    tags            TEXT[]       NOT NULL DEFAULT '{}',
    metadata        JSONB        NOT NULL DEFAULT '{}'::jsonb,
    embedding       VECTOR(1024) NOT NULL,
    embedding_model TEXT         NOT NULL,             -- modelo que gerou o vetor
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- Indice HNSW: deixa a busca por similaridade de cosseno rapida (operador
-- <=>). Com 61 chunks isso nao faz diferenca nenhuma, mas deixo preparado
-- pro dia em que o dicionario crescer.
CREATE INDEX IF NOT EXISTS idx_documents_embedding ON rag.documents USING hnsw (embedding vector_cosine_ops);
-- Filtros por tipo e por tags (ex.: so exemplos de SQL, so chunks de uma tabela)
CREATE INDEX IF NOT EXISTS idx_documents_doc_type  ON rag.documents (doc_type);
CREATE INDEX IF NOT EXISTS idx_documents_tags      ON rag.documents USING gin (tags);

COMMENT ON SCHEMA rag IS 'Base de conhecimento do RAG: dicionario semantico com embeddings.';
COMMENT ON TABLE rag.documents IS '1 linha por chunk do dicionario (metrica, regra, tabela ou exemplo de SQL).';
