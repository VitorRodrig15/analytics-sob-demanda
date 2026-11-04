"""Entregável 2.2 (E2) - Limpeza e carga dos dados do Olist no schema dw (passo A3).

Esse é o script que fecha o ciclo da ingestão: lê os CSVs de data/raw/olist,
aplica cada regra de limpeza que o relatório do A1 (profile_data.py) revelou
ser necessária e grava tudo nas 8 tabelas do schema dw, criadas no A2
(sql/dw_schema.sql). Nenhuma regra aqui foi "achismo" - cada uma corresponde
a um problema real que medi antes de mexer nos dados.

A carga é idempotente de propósito: esvazia as tabelas e carrega tudo de
novo, numa única transação. Isso significa que posso rodar este script
quantas vezes quiser - se uma regra de limpeza mudar amanhã, é só rodar de
novo, sem risco de duplicar nada ou deixar o banco pela metade se algo
falhar no meio do caminho.

Uso (dentro do container):
    docker compose exec app python scripts/load_dw.py             -> limpa e carrega
    docker compose exec app python scripts/load_dw.py --dry-run   -> so limpa e mostra o resumo
"""
import argparse
import io
import os
import unicodedata
from pathlib import Path

import pandas as pd
import psycopg

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "olist"

ZIP_COLUMNS = ["customer_zip_code_prefix", "seller_zip_code_prefix", "geolocation_zip_code_prefix"]

REGION_BY_STATE = {
    "AC": "Norte", "AP": "Norte", "AM": "Norte", "PA": "Norte", "RO": "Norte", "RR": "Norte", "TO": "Norte",
    "AL": "Nordeste", "BA": "Nordeste", "CE": "Nordeste", "MA": "Nordeste", "PB": "Nordeste",
    "PE": "Nordeste", "PI": "Nordeste", "RN": "Nordeste", "SE": "Nordeste",
    "DF": "Centro-Oeste", "GO": "Centro-Oeste", "MT": "Centro-Oeste", "MS": "Centro-Oeste",
    "ES": "Sudeste", "MG": "Sudeste", "RJ": "Sudeste", "SP": "Sudeste",
    "PR": "Sul", "RS": "Sul", "SC": "Sul",
}

# 2 categorias de produto nao tinham traducao no arquivo original do Kaggle -
# tive que traduzir na mao pra nenhum produto ficar sem o campo em ingles.
MISSING_TRANSLATIONS = {
    "pc_gamer": "pc_gamer",
    "portateis_cozinha_e_preparadores_de_alimentos": "portable_kitchen_and_food_preparers",
    "sem_categoria": "no_category",
}

# Limites aproximados do territorio brasileiro. Uso isso so pra descartar as
# ~42 coordenadas que vinham erradas (fora do Brasil) do calculo da media de
# lat/lng de cada CEP - sem isso, a media de alguns CEPs saia deslocada.
BRAZIL_LAT = (-34.0, 5.5)
BRAZIL_LNG = (-74.0, -34.0)


def read_csv(filename: str, date_columns: list[str] | None = None) -> pd.DataFrame:
    # CEP como texto (mantem zero a esquerda); utf-8-sig remove o BOM
    df = pd.read_csv(RAW_DIR / filename, encoding="utf-8-sig", dtype={c: str for c in ZIP_COLUMNS})
    for col in date_columns or []:
        df[col] = pd.to_datetime(df[col], errors="coerce")
    for col in df.columns.intersection(ZIP_COLUMNS):
        df[col] = df[col].str.zfill(5)
    return df


def normalize_city(s: pd.Series) -> pd.Series:
    """'São Paulo ' -> 'sao paulo' (sem acento, minusculo, sem espacos sobrando)."""
    def clean(value):
        if pd.isna(value):
            return value
        text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
        return " ".join(text.lower().split())
    return s.map(clean)


def to_int(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    # Int64 aceita nulos e grava "5" em vez de "5.0" (que o SMALLINT recusaria)
    for col in columns:
        df[col] = df[col].round().astype("Int64")
    return df


# ---------------------------------------------------------------------------
# Limpeza por tabela - cada funcao abaixo resolve um ou mais achados do A1
# ---------------------------------------------------------------------------
def clean_geolocation() -> pd.DataFrame:
    # Aqui que agrego 1 milhao de linhas para 19 mil (1 por CEP). Importante:
    # isso NAO e so "remover duplicata" - a maior parte sao pontos de GPS
    # genuinamente diferentes dentro do mesmo CEP (um CEP de 5 digitos cobre
    # uma regiao inteira, nao um endereco unico). Faco a media de lat/lng e
    # pego a cidade/estado mais frequente de cada CEP.
    geo = read_csv("olist_geolocation_dataset.csv")
    geo["geolocation_city"] = normalize_city(geo["geolocation_city"])
    inside = geo["geolocation_lat"].between(*BRAZIL_LAT) & geo["geolocation_lng"].between(*BRAZIL_LNG)
    zip_col = "geolocation_zip_code_prefix"

    coords = geo[inside].groupby(zip_col)[["geolocation_lat", "geolocation_lng"]].mean()
    # cidade/estado mais frequentes de cada CEP
    place = (
        geo.groupby([zip_col, "geolocation_city", "geolocation_state"]).size()
        .reset_index(name="n")
        .sort_values("n")
        .drop_duplicates(zip_col, keep="last")
        .set_index(zip_col)[["geolocation_city", "geolocation_state"]]
    )
    return place.join(coords).reset_index()[
        [zip_col, "geolocation_lat", "geolocation_lng", "geolocation_city", "geolocation_state"]
    ]


def clean_customers() -> pd.DataFrame:
    # Padronizo a cidade (sem acento, minuscula) e crio a coluna de regiao
    # a partir do estado - o dataset so vem com UF, mas o problema de
    # negocio pede analise "por regiao", entao resolvi isso aqui na carga.
    df = read_csv("olist_customers_dataset.csv")
    df["customer_city"] = normalize_city(df["customer_city"])
    df["customer_region"] = df["customer_state"].map(REGION_BY_STATE)
    return df


def clean_sellers() -> pd.DataFrame:
    df = read_csv("olist_sellers_dataset.csv")
    df["seller_city"] = normalize_city(df["seller_city"])
    df["seller_region"] = df["seller_state"].map(REGION_BY_STATE)
    return df


def clean_products() -> pd.DataFrame:
    # O CSV original vem com "lenght" escrito errado (faltando o "t") em duas
    # colunas - corrijo aqui pra ninguem, nem o agente de IA depois, tropecar
    # nesse erro de digitacao do Kaggle.
    df = read_csv("olist_products_dataset.csv").rename(columns={
        "product_name_lenght": "product_name_length",
        "product_description_lenght": "product_description_length",
    })
    # 610 produtos vinham sem categoria - em vez de descartar (e perder a
    # receita deles), mantenho e marco como "sem_categoria".
    df["product_category_name"] = df["product_category_name"].fillna("sem_categoria")

    translation = read_csv("product_category_name_translation.csv")
    english = dict(zip(translation["product_category_name"], translation["product_category_name_english"]))
    english.update(MISSING_TRANSLATIONS)
    df["product_category_name_english"] = df["product_category_name"].map(english)

    df = to_int(df, [
        "product_name_length", "product_description_length", "product_photos_qty",
        "product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm",
    ])
    return df[[
        "product_id", "product_category_name", "product_category_name_english",
        "product_name_length", "product_description_length", "product_photos_qty",
        "product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm",
    ]]


def clean_orders() -> pd.DataFrame:
    return read_csv("olist_orders_dataset.csv", [
        "order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date",
        "order_delivered_customer_date", "order_estimated_delivery_date",
    ])


def clean_order_items() -> pd.DataFrame:
    df = read_csv("olist_order_items_dataset.csv", ["shipping_limit_date"])
    return to_int(df, ["order_item_id"])


def clean_order_payments() -> pd.DataFrame:
    df = read_csv("olist_order_payments_dataset.csv")
    return to_int(df, ["payment_sequential", "payment_installments"])


def clean_order_reviews() -> pd.DataFrame:
    # 814 avaliacoes tinham o mesmo review_id repetido (o A1 pegou isso) -
    # por isso a chave real da tabela e review_id + order_id, nao so review_id.
    df = read_csv("olist_order_reviews_dataset.csv", ["review_creation_date", "review_answer_timestamp"])
    for col in ["review_comment_title", "review_comment_message"]:
        df[col] = df[col].str.strip().replace("", pd.NA)
    return df.drop_duplicates(subset=["review_id", "order_id"])


# Ordem de carga = ordem das ligacoes (pais antes dos filhos). Preciso respeitar
# essa ordem porque as tabelas tem chave estrangeira entre si - se eu tentar
# carregar order_items antes de orders, o banco recusa.
TABLES = [
    ("geolocation", "olist_geolocation_dataset.csv", clean_geolocation),
    ("customers", "olist_customers_dataset.csv", clean_customers),
    ("sellers", "olist_sellers_dataset.csv", clean_sellers),
    ("products", "olist_products_dataset.csv", clean_products),
    ("orders", "olist_orders_dataset.csv", clean_orders),
    ("order_items", "olist_order_items_dataset.csv", clean_order_items),
    ("order_payments", "olist_order_payments_dataset.csv", clean_order_payments),
    ("order_reviews", "olist_order_reviews_dataset.csv", clean_order_reviews),
]


# ---------------------------------------------------------------------------
# Carga no banco - aqui que a transacao unica e a idempotencia acontecem
# ---------------------------------------------------------------------------
def database_url() -> str:
    url = os.getenv("DATABASE_URL", "postgresql://analytics:analytics@localhost:5432/analytics")
    return url.replace("postgresql+psycopg://", "postgresql://")


def copy_dataframe(cur: psycopg.Cursor, table: str, df: pd.DataFrame) -> None:
    """Grava o DataFrame com COPY, que e muito mais rapido que INSERT linha a
    linha - e por causa disso que a carga das 569.703 linhas leva menos de
    1 minuto, mesmo rodando dentro de uma transacao unica."""
    buffer = io.StringIO()
    df.to_csv(buffer, index=False, header=False, date_format="%Y-%m-%d %H:%M:%S")
    columns = ", ".join(df.columns)
    with cur.copy(f"COPY dw.{table} ({columns}) FROM STDIN WITH (FORMAT csv)") as copy:
        copy.write(buffer.getvalue())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="limpa os dados sem gravar no banco")
    args = parser.parse_args()

    cleaned = {}
    for table, filename, clean in TABLES:
        cleaned[table] = clean()
        print(f"  limpo  {table:<15} {len(cleaned[table]):>8} linhas")

    summary = []
    if args.dry_run:
        print("\n--dry-run: nada foi gravado no banco")
    else:
        # um unico "with": commit no final, rollback automatico se der erro
        with psycopg.connect(database_url()) as conn, conn.cursor() as cur:
            cur.execute("TRUNCATE " + ", ".join(f"dw.{t}" for t, _, _ in TABLES))
            for table, _, _ in TABLES:
                copy_dataframe(cur, table, cleaned[table])
                print(f"  gravado dw.{table}")
            for table, _, _ in TABLES:
                cur.execute(f"SELECT COUNT(*) FROM dw.{table}")
                summary.append((table, cur.fetchone()[0]))

    loaded = dict(summary)
    print(f"\n{'tabela':<16}{'linhas CSV':>12}{'apos limpeza':>14}{'no banco':>10}")
    for table, filename, _ in TABLES:
        raw = len(pd.read_csv(RAW_DIR / filename, usecols=[0]))
        print(f"{table:<16}{raw:>12}{len(cleaned[table]):>14}{loaded.get(table, '-'):>10}")


if __name__ == "__main__":
    main()
