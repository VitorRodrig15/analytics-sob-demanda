"""Entregável 2.3 (E2) - Chunking do dicionário semântico (passo B2).

Com o dicionário validado (B1), o próximo passo foi decidir COMO dividir
esse conhecimento em pedaços para o RAG buscar. A estratégia que escolhi,
já desde a E1 (item 1.4 B), foi chunking por UNIDADE SEMÂNTICA, nunca por
tamanho fixo - cortar um texto a cada N caracteres correria o risco de
separar uma fórmula do seu próprio filtro obrigatório, por exemplo.

Então cada arquivo do dicionário vira chunks do seu jeito:
  - metricas.md        -> 1 chunk por métrica      (doc_type = metric)
  - regras_negocio.md  -> 1 chunk por regra        (doc_type = business_rule)
  - tabelas.md         -> 1 chunk por tabela       (doc_type = table_schema)
  - exemplos_sql.json  -> 1 chunk por exemplo      (doc_type = sql_example)

Cada chunk guarda dois textos separados, e essa separação é proposital:
  - search_text: o que vira embedding - parecido com a forma como o gestor
    pergunta, sem SQL no meio atrapalhando a comparação de significado
  - content:     o que o agente recebe quando o chunk é encontrado - esse
    sim com o SQL de referência completo

Saída: data/processed/chunks.jsonl e o relatório docs/b2_chunks.md. Este
script ainda não gera embeddings - isso é o próximo passo, o bloco C.

Uso (dentro do container):  docker compose exec app python scripts/build_chunks.py
"""
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_DIR = ROOT / "knowledge"
OUTPUT = ROOT / "data" / "processed" / "chunks.jsonl"
REPORT = ROOT / "docs" / "b2_chunks.md"

# Limite conservador: 512 tokens, o padrao dos modelos E5 (era a familia do
# modelo que eu tinha planejado originalmente, antes dele ser descontinuado -
# ver o bloco C). O nemotron-3.5-embed-1b, que acabei usando, aceita textos
# maiores, mas prefiro manter os chunks curtos porque isso deixa a busca
# mais precisa (um chunk focado em um so assunto compara melhor).
MAX_TOKENS = 512

SQL_BLOCK = re.compile(r"```sql\n.*?```", re.DOTALL)
TABLE_NAME = re.compile(r"dw\.\w+")
DOC_TYPE_LABEL = {
    "metric": "Métrica",
    "business_rule": "Regra de negócio",
    "table_schema": "Tabela",
    "sql_example": "Exemplo de SQL validado",
}


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9.]+", "-", text).strip("-")


def split_sections(path: Path) -> list[tuple[str, str]]:
    """Retorna (titulo, corpo) de cada secao '## ' do Markdown; ignora a introducao."""
    parts = re.split(r"^## ", path.read_text(encoding="utf-8"), flags=re.MULTILINE)[1:]
    sections = []
    for part in parts:
        title, _, body = part.partition("\n")
        sections.append((title.strip(), body.strip()))
    return sections


def field(body: str, name: str) -> str:
    """Le um campo no formato '- **Nome:** valor'."""
    match = re.search(rf"\*\*{name}:\*\*\s*(.+)", body)
    return match.group(1).strip() if match else ""


def make_chunk(doc_type, source, title, search_text, content, tags, metadata=None):
    header = f"{DOC_TYPE_LABEL[doc_type]}: {title}"
    return {
        "id": f"{doc_type}:{slugify(title)}",
        "doc_type": doc_type,
        "source": source,
        "title": title,
        # cabecalho de contexto: o chunk faz sentido mesmo lido sozinho
        "search_text": f"{header}\n{search_text}".strip(),
        "content": f"{header}\n\n{content}".strip(),
        "tags": sorted(set(tags)),
        "metadata": metadata or {},
    }


# ---------------------------------------------------------------------------
# Chunkers por tipo de documento
# ---------------------------------------------------------------------------
def metric_chunks() -> list[dict]:
    chunks = []
    for title, body in split_sections(KNOWLEDGE_DIR / "metricas.md"):
        synonyms = [s.strip() for s in field(body, "Sinônimos").split(",") if s.strip()]
        tables = TABLE_NAME.findall(field(body, "Tabelas"))
        chunks.append(make_chunk(
            "metric", "metricas.md", title,
            search_text=SQL_BLOCK.sub("", body),   # sem SQL: so o significado
            content=body,                           # com SQL de referencia
            tags=tables + [slugify(title)],
            metadata={"synonyms": synonyms, "tables": tables,
                      "available": "indisponível" not in field(body, "Definição").lower()},
        ))
    return chunks


def rule_chunks() -> list[dict]:
    return [
        make_chunk("business_rule", "regras_negocio.md", title, body, body,
                   tags=TABLE_NAME.findall(body) + [slugify(title)])
        for title, body in split_sections(KNOWLEDGE_DIR / "regras_negocio.md")
    ]


def table_chunks() -> list[dict]:
    chunks = []
    for title, body in split_sections(KNOWLEDGE_DIR / "tabelas.md"):
        table = TABLE_NAME.search(title).group(0)
        related = [t for t in TABLE_NAME.findall(field(body, "Liga com")) if t != table]
        chunks.append(make_chunk(
            "table_schema", "tabelas.md", title, body, body,
            tags=[table] + related,
            metadata={"table": table, "related_tables": sorted(set(related))},
        ))
    return chunks


def example_chunks() -> list[dict]:
    examples = json.loads((KNOWLEDGE_DIR / "exemplos_sql.json").read_text(encoding="utf-8"))
    chunks = []
    for ex in examples:
        metrics = ", ".join(ex["metricas"])
        # busca pela pergunta (ja vai no cabecalho): e o que mais se parece com a pergunta do usuario
        search_text = f"Intenção: {ex['intencao']}\nMétricas: {metrics}"
        content_parts = [
            f"Pergunta: {ex['pergunta']}",
            f"Intenção: {ex['intencao']}",
            f"Métricas: {metrics}",
            f"Tabelas: {', '.join(ex['tabelas']) or '-'}",
        ]
        if ex.get("observacao"):
            content_parts.append(f"Observação: {ex['observacao']}")
        content_parts.append(f"SQL:\n```sql\n{ex['sql']}\n```" if ex["sql"] else "SQL: não aplicável.")
        chunk = make_chunk(
            "sql_example", "exemplos_sql.json", ex["pergunta"], search_text, "\n".join(content_parts),
            tags=ex["tabelas"] + [ex["intencao"]] + [slugify(m) for m in ex["metricas"]],
            metadata={"example_id": ex["id"], "intent": ex["intencao"],
                      "metrics": ex["metricas"], "tables": ex["tabelas"]},
        )
        chunk["id"] = f"sql_example:{ex['id']}"
        chunks.append(chunk)
    return chunks


# ---------------------------------------------------------------------------
# Contagem de tokens
# ---------------------------------------------------------------------------
def token_counter():
    """Uso o tokenizador real da familia E5 pra medir os tokens, nao uma
    estimativa - quero saber com precisao se algum chunk estoura o limite.
    Se o download falhar (sem internet, por exemplo), caio para uma
    estimativa simples em vez de travar o script."""
    try:
        from tokenizers import Tokenizer
        tokenizer = Tokenizer.from_pretrained("intfloat/e5-large-v2")
        return "tokenizador e5-large-v2", lambda text: len(tokenizer.encode(text).ids)
    except Exception:
        return "estimativa (caracteres / 3.5)", lambda text: round(len(text) / 3.5)


def main() -> None:
    chunks = metric_chunks() + rule_chunks() + table_chunks() + example_chunks()

    ids = [c["id"] for c in chunks]
    duplicated = {i for i in ids if ids.count(i) > 1}
    if duplicated:
        raise SystemExit(f"IDs de chunk repetidos: {duplicated}")

    method, count_tokens = token_counter()
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for chunk in chunks:
        chunk["search_tokens"] = count_tokens(chunk["search_text"])
        chunk["content_chars"] = len(chunk["content"])
        chunk["created_at"] = created_at

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    # ---------------- resumo ----------------
    by_type = {}
    for chunk in chunks:
        by_type.setdefault(chunk["doc_type"], []).append(chunk)

    over_limit = [c for c in chunks if c["search_tokens"] > MAX_TOKENS]
    rows = []
    for doc_type, items in by_type.items():
        tokens = [c["search_tokens"] for c in items]
        rows.append((doc_type, items[0]["source"], len(items), min(tokens),
                     round(sum(tokens) / len(tokens)), max(tokens)))

    print(f"{'doc_type':<15}{'fonte':<20}{'chunks':>7}{'tok min':>9}{'tok medio':>10}{'tok max':>9}")
    for row in rows:
        print(f"{row[0]:<15}{row[1]:<20}{row[2]:>7}{row[3]:>9}{row[4]:>10}{row[5]:>9}")
    print(f"\nTotal: {len(chunks)} chunks | tokens medidos com {method}")
    print(f"Acima do limite de {MAX_TOKENS} tokens: {len(over_limit)}")
    for c in over_limit:
        print(f"  ! {c['id']} ({c['search_tokens']} tokens)")
    print(f"Chunks salvos em {OUTPUT.relative_to(ROOT)}")

    sample = next(c for c in chunks if c["id"] == "metric:ticket-medio")
    lines = [
        "# B2 - Chunks do dicionário semântico",
        "",
        f"**{len(chunks)} chunks** gerados por unidade semântica. "
        f"Tokens do texto de busca medidos com {method}; limite do modelo: {MAX_TOKENS}. "
        f"Chunks acima do limite: **{len(over_limit)}**.",
        "",
        "| doc_type | Fonte | Chunks | Tokens mín. | Tokens médio | Tokens máx. |",
        "|---|---|---|---|---|---|",
        *[f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} |" for r in rows],
        "",
        "## Exemplo de chunk: Ticket médio",
        "",
        "**Texto de busca** (vira embedding, sem SQL):",
        "",
        "```text",
        sample["search_text"],
        "```",
        "",
        "**Conteúdo** (entregue ao agente, com SQL):",
        "",
        "````text",
        sample["content"],
        "````",
        "",
        "**Metadados:**",
        "",
        "```json",
        json.dumps({k: sample[k] for k in ["id", "doc_type", "source", "title", "tags", "metadata",
                                            "search_tokens", "created_at"]},
                   ensure_ascii=False, indent=2),
        "```",
        "",
        "## Todos os chunks",
        "",
        "| id | Título | Tokens de busca | Tamanho do conteúdo (caracteres) |",
        "|---|---|---|---|",
        *[f"| `{c['id']}` | {c['title']} | {c['search_tokens']} | {c['content_chars']} |" for c in chunks],
    ]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Relatorio salvo em {REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
