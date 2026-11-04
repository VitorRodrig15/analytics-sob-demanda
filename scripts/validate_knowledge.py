"""Entregável 2.2/2.3 (E2) - Valida os SQLs do dicionário semântico (passo B1).

Escrevi o dicionário semântico (a pasta knowledge/, com as 18 métricas, as
13 regras de negócio, as 8 tabelas e os 22 exemplos de pergunta -> SQL) para
ser a fonte única da verdade que os agentes vão consultar. Mas de nada
adianta um dicionário bonito se o SQL de referência dentro dele estiver
quebrado - então este script pega cada bloco de SQL dos arquivos .md e o
campo "sql" de exemplos_sql.json, e executa de verdade contra o banco.

Tudo roda em transação SOMENTE LEITURA, então não corro risco nenhum de
alterar dados só por estar validando. Se algum SQL falhar aqui, é sinal de
que preciso corrigir o dicionário antes de seguir para o chunking (B2).

Gera o relatorio docs/b1_validacao_sql.md.

Uso (dentro do container):  docker compose exec app python scripts/validate_knowledge.py
"""
import json
import os
import re
import sys
import time
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_DIR = ROOT / "knowledge"
REPORT = ROOT / "docs" / "b1_validacao_sql.md"

SQL_BLOCK = re.compile(r"```sql\n(.*?)```", re.DOTALL)
SECTION = re.compile(r"^## (.+)$", re.MULTILINE)


def database_url() -> str:
    url = os.getenv("DATABASE_URL", "postgresql://analytics:analytics@localhost:5432/analytics")
    return url.replace("postgresql+psycopg://", "postgresql://")


def collect_queries() -> list[tuple[str, str, str]]:
    """Varre o dicionario inteiro e devolve (arquivo, item, sql) de cada
    consulta encontrada - e assim que junto os 38 SQLs que testo aqui."""
    queries = []
    for md_file in sorted(KNOWLEDGE_DIR.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        for match in SQL_BLOCK.finditer(text):
            # titulo da secao (##) onde o bloco de SQL esta
            titles = SECTION.findall(text[: match.start()])
            queries.append((md_file.name, titles[-1] if titles else "-", match.group(1)))

    examples = json.loads((KNOWLEDGE_DIR / "exemplos_sql.json").read_text(encoding="utf-8"))
    for ex in examples:
        if ex["sql"]:
            queries.append(("exemplos_sql.json", f'{ex["id"]} - {ex["pergunta"]}', ex["sql"]))
    return queries


def main() -> None:
    results = []
    with psycopg.connect(database_url(), autocommit=True) as conn:
        for source, item, sql in collect_queries():
            start = time.perf_counter()
            try:
                with conn.transaction(), conn.cursor() as cur:
                    cur.execute("SET TRANSACTION READ ONLY")
                    cur.execute("SET LOCAL statement_timeout = '30s'")
                    cur.execute(sql)
                    rows = cur.fetchall()
                    first = dict(zip([d.name for d in cur.description], rows[0])) if rows else {}
                status = "OK" if rows else "SEM LINHAS"
                detail = ", ".join(f"{k}={v}" for k, v in list(first.items())[:3])
            except psycopg.Error as exc:
                rows, status, detail = [], "ERRO", str(exc).splitlines()[0]
            elapsed = (time.perf_counter() - start) * 1000
            results.append((source, item, status, len(rows), elapsed, detail))
            print(f"{status:<10} {elapsed:7.0f} ms  {source:<20} {item}")

    ok = sum(r[2] == "OK" for r in results)
    print(f"\n{ok}/{len(results)} SQLs validados")

    lines = [
        "# B1 - Validação dos SQLs do dicionário semântico",
        "",
        f"**{ok} de {len(results)} SQLs executados com sucesso** (transação somente leitura).",
        "",
        "| Arquivo | Item | Status | Linhas | Tempo (ms) | Primeira linha |",
        "|---|---|---|---|---|---|",
    ]
    for source, item, status, n, elapsed, detail in results:
        lines.append(f"| {source} | {item} | {status} | {n} | {elapsed:.0f} | {detail.replace('|', '/')} |")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Relatorio salvo em {REPORT.relative_to(ROOT)}")

    sys.exit(0 if ok == len(results) else 1)


if __name__ == "__main__":
    main()
