# tests/test_validador.py
from scripts.validador import validar_sql


def test_aceita_select_simples_no_schema_dw():
    r = validar_sql("SELECT order_id FROM dw.orders LIMIT 10")
    assert r.ok is True


def test_aceita_with_select_no_schema_dw():
    r = validar_sql("WITH t AS (SELECT * FROM dw.orders) SELECT * FROM t")
    assert r.ok is True


def test_aceita_ponto_e_virgula_dentro_de_string_literal():
    # a regra antiga da E4 (tools.py) rejeitava isso por conter ";" no texto -
    # o sqlglot entende que e so um literal, nao um separador de statement
    sql = "SELECT * FROM dw.order_reviews WHERE review_comment_message = 'Otimo; recomendo'"
    r = validar_sql(sql)
    assert r.ok is True


def test_rejeita_insert():
    r = validar_sql("INSERT INTO dw.orders (order_id) VALUES ('x')")
    assert r.ok is False
    assert r.motivo


def test_rejeita_multiplas_instrucoes():
    r = validar_sql("SELECT * FROM dw.orders; DROP TABLE dw.orders")
    assert r.ok is False


def test_rejeita_tabela_fora_do_schema_dw():
    r = validar_sql("SELECT * FROM rag.chunks")
    assert r.ok is False


def test_rejeita_sql_sintaticamente_invalido_sem_lancar_excecao():
    r = validar_sql("SELECT FROM WHERE dw.orders")
    assert r.ok is False
    assert r.motivo


def test_rejeita_tabela_fora_do_schema_dw_escondida_atras_de_cte_de_escopo_diferente():
    # uma CTE chamada "orders", definida dentro de uma subquery (IN (...)),
    # nao pode "esconder" uma referencia de FROM orders no nivel de cima -
    # essa CTE tem escopo proprio, nao e visivel la fora. O FROM orders
    # externo e uma tabela de verdade, sem schema, e deve ser rejeitado.
    sql = (
        "SELECT * FROM orders WHERE order_id IN "
        "(WITH orders AS (SELECT 1 AS x) SELECT x FROM orders)"
    )
    r = validar_sql(sql)
    assert r.ok is False
