"""Entregável 2.4 (E2) - Gera os embeddings e grava no pgvector (passo C2).

Esta é a etapa que transforma os 61 chunks do dicionário (gerados no B2) em
vetores de verdade, prontos para busca por similaridade. Leio
data/processed/chunks.jsonl, envio o search_text de cada chunk ao modelo de
embedding da NVIDIA (em um único lote, não um por um) e gravo tudo na
tabela rag.documents (schema criado por sql/rag_schema.sql).

Um detalhe que vale registrar aqui: o modelo de embedding que eu tinha
planejado originalmente (nv-embedqa-e5-v5) foi descontinuado pela NVIDIA em
25/08/2026, no meio do desenvolvimento da E2. Testei as alternativas
disponíveis com perguntas em português e acabei escolhendo o
nemotron-3.5-embed-1b - mesma precisão do modelo de 8B, só que 10x mais
rápido. É por isso que o modelo e a dimensão do vetor vêm de variável de
ambiente, e não estão fixos no código: se a NVIDIA descontinuar este
também, troco só o .env.

A carga é idempotente, igual à do load_dw.py: esvazia rag.documents e grava
de novo, numa única transação.

Uso (dentro do container):
    docker compose exec app python scripts/embed_chunks.py             -> gera e grava
    docker compose exec app python scripts/embed_chunks.py --dry-run   -> so gera, sem gravar
"""
import argparse
import json
import os
import time
from pathlib import Path

import psycopg
from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings

ROOT = Path(__file__).resolve().parents[1]
CHUNKS = ROOT / "data" / "processed" / "chunks.jsonl"
SCHEMA_SQL = ROOT / "sql" / "rag_schema.sql"

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nvidia/nemotron-3.5-embed-1b")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))


def database_url() -> str:
    url = os.getenv("DATABASE_URL", "postgresql://analytics:analytics@localhost:5432/analytics")
    return url.replace("postgresql+psycopg://", "postgresql://")


def load_chunks() -> list[dict]:
    with CHUNKS.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def embed(texts: list[str]) -> list[list[float]]:
    """Gero os embeddings como 'passage' (documento), nao como 'query'. Esses
    dois tipos sao tratados de forma levemente diferente pelo modelo, e usar
    o certo em cada ponta (passage aqui, query na busca em search.py) deixa
    a comparacao de similaridade mais precisa."""
    client = NVIDIAEmbeddings(
        model=EMBEDDING_MODEL,
        api_key=os.environ["NVIDIA_API_KEY"],
        dimensions=EMBEDDING_DIM,
        truncate="END",
    )
    return client.embed_documents(texts)


def to_pgvector(values: list[float]) -> str:
    return "[" + ",".join(f"{v:.7f}" for v in values) + "]"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="gera os embeddings sem gravar no banco")
    args = parser.parse_args()

    chunks = load_chunks()
    print(f"{len(chunks)} chunks lidos de {CHUNKS.relative_to(ROOT)}")
    print(f"Modelo: {EMBEDDING_MODEL} | dimensoes: {EMBEDDING_DIM}")

    start = time.perf_counter()
    vectors = embed([c["search_text"] for c in chunks])
    print(f"{len(vectors)} embeddings gerados em {time.perf_counter() - start:.1f}s")

    wrong = [c["id"] for c, v in zip(chunks, vectors) if len(v) != EMBEDDING_DIM]
    if wrong:
        raise SystemExit(f"Dimensao diferente de {EMBEDDING_DIM} em: {wrong}")
    print(f"Amostra ({chunks[0]['id']}): {[round(x, 4) for x in vectors[0][:5]]} ...")

    if args.dry_run:
        print("\n--dry-run: nada foi gravado no banco")
        return

    rows = [
        (c["id"], c["doc_type"], c["source"], c["title"], c["search_text"], c["content"],
         c["tags"], json.dumps(c["metadata"], ensure_ascii=False), to_pgvector(v),
         EMBEDDING_MODEL, c["created_at"])
        for c, v in zip(chunks, vectors)
    ]
    # um unico "with": commit no final, rollback automatico se der erro
    with psycopg.connect(database_url()) as conn, conn.cursor() as cur:
        cur.execute(SCHEMA_SQL.read_text(encoding="utf-8"))
        cur.execute("TRUNCATE rag.documents")
        cur.executemany(
            """
            INSERT INTO rag.documents
                (id, doc_type, source, title, search_text, content, tags, metadata,
                 embedding, embedding_model, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::vector, %s, %s)
            """,
            rows,
        )
        cur.execute("""
            SELECT doc_type, COUNT(*), MIN(vector_dims(embedding))
            FROM rag.documents GROUP BY doc_type ORDER BY doc_type
        """)
        summary = cur.fetchall()

    print(f"\n{'doc_type':<16}{'chunks':>8}{'dimensoes':>11}")
    for doc_type, total, dims in summary:
        print(f"{doc_type:<16}{total:>8}{dims:>11}")
    print(f"{'total':<16}{sum(r[1] for r in summary):>8}")
    print("\nGravado em rag.documents")


if __name__ == "__main__":
    main()
