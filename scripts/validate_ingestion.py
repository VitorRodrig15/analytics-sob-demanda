"""Entregável 2.5 (E2) - Validação da ingestão, o fechamento da semana (passo D1).

Depois de montar o ambiente (2.1), carregar os dados (2.2), escrever e
dividir o dicionário (2.3) e gerar os embeddings (2.4), este script é o meu
"exame geral": reúne numa passada só todas as evidências de que a E2
funcionou de ponta a ponta, em vez de eu confiar de olho que cada peça
separada deu certo.

As 5 frentes que confiro:
  1. Ambiente: PostgreSQL + pgvector realmente ativos
  2. Dados de negocio: linhas por tabela do dw batendo com o esperado dos CSVs
  3. Base vetorial: chunks por tipo, dimensao do vetor, modelo e indice HNSW
  4. Amostra de embeddings (pra mostrar que nao sao so NULLs)
  5. Busca de teste: 12 perguntas em portugues, escritas com palavras
     diferentes das do dicionario de proposito, pra provar que a busca
     funciona por significado e nao so por coincidencia de texto

Tudo somente leitura - nada e alterado no banco so por estar validando.
Gera o relatorio docs/d1_validacao_ingestao.md, que uso como evidencia na
apresentacao semanal.

Uso (dentro do container):  docker compose exec app python scripts/validate_ingestion.py
"""
import json
import os
import sys
from pathlib import Path

import pandas as pd
import psycopg
from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "olist"
CHUNKS = ROOT / "data" / "processed" / "chunks.jsonl"
REPORT = ROOT / "docs" / "d1_validacao_ingestao.md"

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nvidia/nemotron-3.5-embed-1b")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))
TOP_K = 3
MIN_HIT_RATE = 0.8

# tabela do dw -> CSV de origem
DW_TABLES = {
    "geolocation": "olist_geolocation_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "products": "olist_products_dataset.csv",
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
}

# As 12 perguntas de teste - escrevi cada uma pensando em como um gestor de
# verdade perguntaria, nunca copiando o texto do dicionario. Qualquer um dos
# ids esperados aparecendo entre os 3 primeiros resultados conta como acerto.
SEARCH_TESTS = [
    ("Qual o valor médio gasto em cada compra?",
     {"metric:ticket-medio", "sql_example:ex03"}),
    ("Quantos lojistas pararam de vender em cada região?",
     {"metric:churn-de-vendedores", "sql_example:ex21"}),
    ("As entregas estão chegando dentro do prazo prometido?",
     {"metric:entregas-no-prazo", "metric:atraso-medio", "sql_example:ex09"}),
    ("Qual o lucro que tivemos por categoria?",
     {"metric:margem-de-contribuicao", "sql_example:ex22", "business_rule:metricas-indisponiveis"}),
    ("Como contar clientes sem repetir a mesma pessoa?",
     {"business_rule:identificacao-do-cliente", "metric:clientes-unicos"}),
    ("Quais informações existem sobre as formas de pagamento?",
     {"table_schema:dw.order-payments-pagamentos"}),
    ("Que período devo usar quando pedem o último trimestre?",
     {"business_rule:datas-relativas-ultimo-mes-ultimo-trimestre"}),
    ("Os clientes estão satisfeitos com as compras?",
     {"metric:nota-media-de-avaliacao", "metric:avaliacoes-positivas-e-negativas", "sql_example:ex13"}),
    ("Quais tipos de produto mais faturam?",
     {"sql_example:ex16", "metric:receita"}),
    ("Quanto o frete representa nas vendas do Norte?",
     {"metric:percentual-do-frete-sobre-a-receita", "sql_example:ex10"}),
    ("A consulta pode apagar ou alterar dados?",
     {"business_rule:seguranca-e-boas-praticas-de-sql"}),
    ("Quantos pedidos foram cancelados este ano?",
     {"metric:taxa-de-cancelamento", "sql_example:ex15"}),
]

SEARCH_SQL = """
    SELECT id, doc_type, title, 1 - (embedding <=> %(q)s::vector) AS similaridade
    FROM rag.documents
    ORDER BY embedding <=> %(q)s::vector
    LIMIT %(k)s
"""


def database_url() -> str:
    url = os.getenv("DATABASE_URL", "postgresql://analytics:analytics@localhost:5432/analytics")
    return url.replace("postgresql+psycopg://", "postgresql://")


def to_pgvector(values: list[float]) -> str:
    return "[" + ",".join(f"{v:.7f}" for v in values) + "]"


def expected_dw_rows() -> dict[str, tuple[int, int]]:
    """(linhas no CSV, linhas esperadas no banco). Geolocation e agregada por CEP."""
    expected = {}
    for table, filename in DW_TABLES.items():
        first_col = pd.read_csv(RAW_DIR / filename, usecols=[0], dtype=str).iloc[:, 0]
        expected[table] = (len(first_col), first_col.nunique() if table == "geolocation" else len(first_col))
    return expected


def main() -> None:
    checks = []          # (verificacao, ok, detalhe)
    report = ["# D1 - Validação da ingestão (entregável 2.5)", ""]

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append((name, ok, detail))
        print(f"  [{'OK' if ok else 'FALHOU'}] {name}: {detail}")

    with psycopg.connect(database_url()) as conn:
        conn.read_only = True
        cur = conn.cursor()

        # ---------------- 1. ambiente ----------------
        print("1. Ambiente")
        pg_version = cur.execute("SHOW server_version").fetchone()[0]
        vector_version = cur.execute(
            "SELECT extversion FROM pg_extension WHERE extname = 'vector'").fetchone()
        check("PostgreSQL + pgvector", vector_version is not None,
              f"PostgreSQL {pg_version}, pgvector {vector_version[0] if vector_version else '-'}")

        # ---------------- 2. dados de negocio ----------------
        print("2. Dados de negocio (schema dw)")
        dw_rows = []
        for table, (csv_rows, expected) in expected_dw_rows().items():
            loaded = cur.execute(f"SELECT COUNT(*) FROM dw.{table}").fetchone()[0]
            dw_rows.append((table, csv_rows, expected, loaded))
            check(f"dw.{table}", loaded == expected, f"{loaded} linhas (esperado {expected})")

        # ---------------- 3. base vetorial ----------------
        print("3. Base vetorial (schema rag)")
        with CHUNKS.open(encoding="utf-8") as f:
            chunk_types = pd.Series([json.loads(line)["doc_type"] for line in f if line.strip()])
        by_type = dict(cur.execute(
            "SELECT doc_type, COUNT(*) FROM rag.documents GROUP BY doc_type").fetchall())
        for doc_type, expected in chunk_types.value_counts().sort_index().items():
            check(f"chunks {doc_type}", by_type.get(doc_type) == expected,
                  f"{by_type.get(doc_type, 0)} no banco (esperado {expected})")

        total, null_vectors, dims, models = cur.execute("""
            SELECT COUNT(*), COUNT(*) FILTER (WHERE embedding IS NULL),
                   ARRAY_AGG(DISTINCT vector_dims(embedding)), ARRAY_AGG(DISTINCT embedding_model)
            FROM rag.documents
        """).fetchone()
        check("embeddings preenchidos", null_vectors == 0, f"{total - null_vectors} de {total}")
        check("dimensão dos vetores", dims == [EMBEDDING_DIM], f"{dims}")
        check("modelo único", models == [EMBEDDING_MODEL], f"{models}")
        hnsw = cur.execute("""
            SELECT indexname FROM pg_indexes
            WHERE schemaname = 'rag' AND indexdef ILIKE '%hnsw%'
        """).fetchone()
        check("índice HNSW", hnsw is not None, hnsw[0] if hnsw else "não encontrado")

        # ---------------- 4. amostra de embeddings ----------------
        samples = cur.execute("""
            SELECT id, embedding::text FROM rag.documents
            WHERE id IN ('metric:ticket-medio', 'business_rule:status-do-pedido', 'sql_example:ex21')
            ORDER BY id
        """).fetchall()

        # ---------------- 5. busca de teste ----------------
        print("5. Busca por similaridade")
        embedder = NVIDIAEmbeddings(model=EMBEDDING_MODEL, api_key=os.environ["NVIDIA_API_KEY"],
                                    dimensions=EMBEDDING_DIM, truncate="END")
        searches = []
        for question, expected_ids in SEARCH_TESTS:
            query_vector = to_pgvector(embedder.embed_query(question))
            results = cur.execute(SEARCH_SQL, {"q": query_vector, "k": TOP_K}).fetchall()
            ids = [r[0] for r in results]
            rank = next((i + 1 for i, doc_id in enumerate(ids) if doc_id in expected_ids), None)
            searches.append((question, results, rank))
            print(f"  {'OK ' if rank else 'ERR'} {question} -> {ids[0]} ({results[0][3]:.3f})")

    hits = sum(1 for _, _, rank in searches if rank)
    hits_top1 = sum(1 for _, _, rank in searches if rank == 1)
    check(f"busca: acerto entre os {TOP_K} primeiros", hits / len(searches) >= MIN_HIT_RATE,
          f"{hits}/{len(searches)} ({hits / len(searches):.0%}); 1º lugar: {hits_top1}/{len(searches)}")

    # ---------------- relatorio ----------------
    passed = sum(ok for _, ok, _ in checks)
    report += [
        f"**{passed} de {len(checks)} verificações aprovadas.**",
        "",
        "## Resumo das verificações",
        "",
        "| Verificação | Resultado | Detalhe |",
        "|---|---|---|",
        *[f"| {name} | {'✅' if ok else '❌'} | {detail} |" for name, ok, detail in checks],
        "",
        "## Dados de negócio: CSV x banco",
        "",
        "| Tabela | Linhas no CSV | Esperado no banco | No banco |",
        "|---|---|---|---|",
        *[f"| dw.{t} | {c:,} | {e:,} | {l:,} |".replace(",", ".") for t, c, e, l in dw_rows],
        "",
        "`geolocation` é agregada para 1 linha por CEP (decisão do A3); as demais devem bater 1 para 1.",
        "",
        "## Amostra de embeddings (5 primeiros de 1024 valores)",
        "",
        "| Chunk | Início do vetor |",
        "|---|---|",
        *[f"| `{doc_id}` | `{vec[:80]}...` |" for doc_id, vec in samples],
        "",
        f"## Busca de teste (top {TOP_K} por similaridade de cosseno)",
        "",
        "SQL usado na busca (o vetor da pergunta é gerado com o mesmo modelo, tipo *query*):",
        "",
        "```sql",
        SEARCH_SQL.strip().replace("%(q)s", ":vetor_da_pergunta").replace("%(k)s", str(TOP_K)),
        "```",
        "",
        f"**Acerto entre os {TOP_K} primeiros: {hits}/{len(searches)}** · "
        f"**Acerto em 1º lugar: {hits_top1}/{len(searches)}**",
        "",
    ]
    for question, results, rank in searches:
        status = f"✅ acerto na posição {rank}" if rank else "❌ não encontrado"
        report += [f"### {question}", "", status, "", "| # | Chunk | Similaridade |", "|---|---|---|"]
        report += [f"| {i} | `{r[0]}` | {r[3]:.3f} |" for i, r in enumerate(results, 1)]
        report.append("")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(report), encoding="utf-8")
    print(f"\n{passed}/{len(checks)} verificacoes aprovadas")
    print(f"Relatorio salvo em {REPORT.relative_to(ROOT)}")
    sys.exit(0 if passed == len(checks) else 1)


if __name__ == "__main__":
    main()
