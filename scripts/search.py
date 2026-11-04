"""Entregável 3.1 (E3) - Módulo de Recuperação (Retrieval) + CLI de busca.

Essa busca por similaridade eu já tinha esboçado lá na validação da E2 (o
D2), mas só funcionava como um script que eu rodava na mão e lia o
resultado no terminal. Nesta entrega arrumei isso direito: separei a lógica
numa função de verdade, retrieve(), que é o módulo de recuperação
propriamente dito pedido pelo entregável. Dada uma pergunta em linguagem
natural, ela devolve os K chunks mais relevantes de rag.documents, cada um
com o score de similaridade de cosseno.

A diferença que mais importa aqui: antes eu só conseguia ver o resultado na
tela; agora retrieve() pode ser importada por outro código. É exatamente
isso que o pipeline RAG inteiro (3.3) precisou - ele chama essa função por
dentro, sem passar pelo terminal.

O resto do arquivo continua sendo o CLI de antes, só que agora chamando
retrieve() por baixo - útil para testar uma busca na mão, sem rodar o
pipeline inteiro (e sem esperar a LLM, que é lenta).

Uso como módulo (de outro script em scripts/):
    from search import retrieve
    chunks = retrieve("qual o ticket medio?", k=3)

Uso como CLI (dentro do container):
    docker compose exec app python scripts/search.py "qual o ticket medio por regiao?"
    docker compose exec app python scripts/search.py "pergunta" --k 5 --tipo sql_example
"""
import argparse
import os
import warnings
from dataclasses import dataclass

import psycopg
from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings

warnings.filterwarnings("ignore")

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nvidia/nemotron-3.5-embed-1b")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))
DOC_TYPES = ["metric", "business_rule", "table_schema", "sql_example"]

SEARCH_SQL = """
    SELECT id, doc_type, title, content, 1 - (embedding <=> %(q)s::vector) AS similaridade
    FROM rag.documents
    WHERE %(tipo)s::text IS NULL OR doc_type = %(tipo)s
    ORDER BY embedding <=> %(q)s::vector
    LIMIT %(k)s
"""


@dataclass
class RetrievedChunk:
    """Um chunk encontrado na busca, com o score de similaridade da pergunta."""
    id: str
    doc_type: str
    title: str
    content: str
    similarity: float


def database_url() -> str:
    url = os.getenv("DATABASE_URL", "postgresql://analytics:analytics@localhost:5432/analytics")
    return url.replace("postgresql+psycopg://", "postgresql://")


def to_pgvector(values: list[float]) -> str:
    return "[" + ",".join(f"{v:.7f}" for v in values) + "]"


def retrieve(pergunta: str, k: int = 3, tipo: str | None = None) -> list[RetrievedChunk]:
    """O coracao do entregavel 3.1: busca os k chunks mais parecidos com a
    pergunta em rag.documents, por similaridade de cosseno.

    tipo filtra por doc_type (metric, business_rule, table_schema, sql_example);
    None busca em todos os tipos. Conexao somente leitura, fecha sozinha ao sair -
    nada aqui pode alterar dado nenhum no banco.
    """
    embedder = NVIDIAEmbeddings(model=EMBEDDING_MODEL, api_key=os.environ["NVIDIA_API_KEY"],
                                dimensions=EMBEDDING_DIM, truncate="END")
    vector = to_pgvector(embedder.embed_query(pergunta))

    with psycopg.connect(database_url()) as conn:
        conn.read_only = True
        rows = conn.execute(SEARCH_SQL, {"q": vector, "tipo": tipo, "k": k}).fetchall()

    return [RetrievedChunk(id=r[0], doc_type=r[1], title=r[2], content=r[3], similarity=r[4])
            for r in rows]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pergunta")
    parser.add_argument("--k", type=int, default=3, help="quantidade de chunks (padrao 3)")
    parser.add_argument("--tipo", choices=DOC_TYPES, help="filtrar por tipo de chunk")
    parser.add_argument("--conteudo", action="store_true", help="mostrar o conteudo do 1o chunk")
    args = parser.parse_args()

    chunks = retrieve(args.pergunta, k=args.k, tipo=args.tipo)

    print(f'\nPergunta: "{args.pergunta}"\n')
    print(f"{'#':<3}{'similaridade':<14}{'tipo':<15}titulo")
    for i, chunk in enumerate(chunks, 1):
        print(f"{i:<3}{chunk.similarity:<14.3f}{chunk.doc_type:<15}{chunk.title}")
    if args.conteudo and chunks:
        print(f"\n--- Conteudo entregue ao agente ({chunks[0].id}) ---\n{chunks[0].content}")


if __name__ == "__main__":
    main()
