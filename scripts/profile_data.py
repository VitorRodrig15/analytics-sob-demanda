"""Entregável 2.2 (E2) - Análise de qualidade dos dados brutos do Olist (passo A1).

Este é o primeiro script que escrevi na E2, e de propósito: antes de limpar
qualquer coisa, eu precisava entender o que realmente tinha em mãos. Ele lê
os 9 CSVs de data/raw/olist e gera um relatório de qualidade em
docs/a1_perfil_dados.md, cobrindo volume, tipos de coluna, percentual de
nulos, linhas duplicadas, se as chaves são realmente únicas, se as ligações
entre as tabelas batem (integridade referencial) e o período coberto pelas
datas.

Foi esse relatório que revelou os problemas reais do dataset - como a
geolocalização com centenas de milhares de linhas repetidas, os 814
`review_id` duplicados e o fato de que os dados confiáveis vão só até
agosto de 2018. Cada regra de limpeza que apliquei depois no load_dw.py
(entregável 2.2, passo A3) nasceu de um número que apareceu aqui.

Uso (dentro do container):  docker compose exec app python scripts/profile_data.py
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "olist"
REPORT = ROOT / "docs" / "a1_perfil_dados.md"

# Mapa das 9 tabelas do Olist: nome curto que uso no resto do script -> (arquivo no
# CSV, coluna(s) que deveriam ser a chave primaria). geolocation nao tem chave
# primaria de verdade no arquivo bruto, por isso fica com None aqui.
TABLES = {
    "customers": ("olist_customers_dataset.csv", ["customer_id"]),
    "geolocation": ("olist_geolocation_dataset.csv", None),
    "orders": ("olist_orders_dataset.csv", ["order_id"]),
    "order_items": ("olist_order_items_dataset.csv", ["order_id", "order_item_id"]),
    "order_payments": ("olist_order_payments_dataset.csv", ["order_id", "payment_sequential"]),
    "order_reviews": ("olist_order_reviews_dataset.csv", ["review_id"]),
    "products": ("olist_products_dataset.csv", ["product_id"]),
    "sellers": ("olist_sellers_dataset.csv", ["seller_id"]),
    "category_translation": ("product_category_name_translation.csv", ["product_category_name"]),
}

# Colunas de data de cada tabela, convertidas para datetime so para medir o
# periodo coberto (foi assim que descobri que os dados confiaveis terminam
# em agosto de 2018, e nao em outubro como o CSV sugere a primeira vista).
DATE_COLUMNS = {
    "orders": [
        "order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date",
        "order_delivered_customer_date", "order_estimated_delivery_date",
    ],
    "order_items": ["shipping_limit_date"],
    "order_reviews": ["review_creation_date", "review_answer_timestamp"],
}

# As ligacoes que testo (tabela filha, coluna) -> (tabela pai, coluna): confiro
# se todo valor da coluna filha realmente existe na tabela pai. Foi essa
# checagem que me deu confianca de que o Olist tem boa integridade - as
# tabelas principais bateram 100%, so geolocation e categoria tiveram furos.
FOREIGN_KEYS = [
    (("orders", "customer_id"), ("customers", "customer_id")),
    (("order_items", "order_id"), ("orders", "order_id")),
    (("order_items", "product_id"), ("products", "product_id")),
    (("order_items", "seller_id"), ("sellers", "seller_id")),
    (("order_payments", "order_id"), ("orders", "order_id")),
    (("order_reviews", "order_id"), ("orders", "order_id")),
    (("products", "product_category_name"), ("category_translation", "product_category_name")),
    (("customers", "customer_zip_code_prefix"), ("geolocation", "geolocation_zip_code_prefix")),
    (("sellers", "seller_zip_code_prefix"), ("geolocation", "geolocation_zip_code_prefix")),
]

# colunas categoricas cuja distribuicao ajuda a entender o negocio
DISTRIBUTIONS = [
    ("orders", "order_status"),
    ("order_payments", "payment_type"),
    ("order_reviews", "review_score"),
    ("customers", "customer_state"),
]


def load_tables() -> dict[str, pd.DataFrame]:
    tables = {}
    for name, (filename, _) in TABLES.items():
        # CEP como texto para nao perder zeros a esquerda; utf-8-sig remove o BOM
        df = pd.read_csv(
            RAW_DIR / filename,
            encoding="utf-8-sig",
            dtype={c: str for c in ["customer_zip_code_prefix", "seller_zip_code_prefix",
                                     "geolocation_zip_code_prefix"]},
        )
        for col in DATE_COLUMNS.get(name, []):
            df[col] = pd.to_datetime(df[col], errors="coerce")
        tables[name] = df
    return tables


def overview(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for name, df in tables.items():
        pk = TABLES[name][1]
        pk_dups = int(df.duplicated(subset=pk).sum()) if pk else None
        rows.append({
            "tabela": name,
            "linhas": len(df),
            "colunas": df.shape[1],
            "linhas duplicadas": int(df.duplicated().sum()),
            "chave": ", ".join(pk) if pk else "-",
            "chaves repetidas": "-" if pk_dups is None else pk_dups,
            "memoria (MB)": round(df.memory_usage(deep=True).sum() / 1e6, 1),
        })
    return pd.DataFrame(rows)


def column_profile(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for col in df.columns:
        s = df[col]
        non_null = s.dropna()
        if pd.api.types.is_numeric_dtype(s) or pd.api.types.is_datetime64_any_dtype(s):
            value_range = f"{non_null.min()} -> {non_null.max()}" if len(non_null) else "-"
        else:
            value_range = "ex.: " + str(non_null.iloc[0])[:40] if len(non_null) else "-"
        rows.append({
            "coluna": col,
            "tipo": str(s.dtype),
            "nulos": int(s.isna().sum()),
            "% nulos": round(s.isna().mean() * 100, 2),
            "valores distintos": int(s.nunique()),
            "faixa / exemplo": value_range,
        })
    return pd.DataFrame(rows)


def integrity(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for (child, ccol), (parent, pcol) in FOREIGN_KEYS:
        values = tables[child][ccol].dropna()
        orphans = ~values.isin(set(tables[parent][pcol]))
        rows.append({
            "ligacao": f"{child}.{ccol} -> {parent}.{pcol}",
            "registros": len(values),
            "sem correspondencia": int(orphans.sum()),
            "% sem correspondencia": round(orphans.mean() * 100, 2),
            "exemplos": ", ".join(values[orphans].astype(str).unique()[:3]),
        })
    return pd.DataFrame(rows)


def date_ranges(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for name, cols in DATE_COLUMNS.items():
        for col in cols:
            s = tables[name][col]
            rows.append({"coluna": f"{name}.{col}", "inicio": s.min(), "fim": s.max(),
                         "nulos": int(s.isna().sum())})
    return pd.DataFrame(rows)


def distribution(df: pd.DataFrame, col: str) -> pd.DataFrame:
    counts = df[col].value_counts(dropna=False)
    return pd.DataFrame({
        col: counts.index.astype(str),
        "qtd": counts.values,
        "%": (counts.values / counts.sum() * 100).round(2),
    })


def md(df: pd.DataFrame) -> str:
    return df.to_markdown(index=False)


def build_report(tables: dict[str, pd.DataFrame]) -> str:
    parts = [
        "# A1 - Perfil dos dados brutos (Olist)",
        "",
        f"Fonte: `data/raw/olist/` - {len(tables)} arquivos CSV.",
        "",
        "## 1. Visao geral",
        "",
        md(overview(tables)),
        "",
        "## 2. Integridade entre tabelas",
        "",
        "Registros da tabela filha cujo valor nao existe na tabela pai.",
        "",
        md(integrity(tables)),
        "",
        "## 3. Periodo coberto pelas datas",
        "",
        md(date_ranges(tables)),
        "",
        "## 4. Distribuicoes de colunas-chave",
        "",
    ]
    for name, col in DISTRIBUTIONS:
        parts += [f"### {name}.{col}", "", md(distribution(tables[name], col)), ""]
    parts += ["## 5. Perfil por coluna", ""]
    for name, df in tables.items():
        parts += [f"### {name}", "", md(column_profile(df)), ""]
    return "\n".join(parts)


def main() -> None:
    tables = load_tables()
    print(overview(tables).to_string(index=False))
    print()
    print(integrity(tables).to_string(index=False))

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(build_report(tables), encoding="utf-8")
    print(f"\nRelatorio salvo em {REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
