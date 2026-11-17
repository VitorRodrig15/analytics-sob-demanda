# tests/test_execucao_resposta.py
from execucao_resposta import executar_sql


def test_executar_sql_sucesso():
    resultado, erro = executar_sql("SELECT COUNT(*) AS total FROM dw.orders")
    assert erro is None
    assert resultado["total_retornado"] == 1
    assert resultado["linhas"][0]["total"] > 0


def test_executar_sql_erro_de_sintaxe_nao_derruba_processo():
    resultado, erro = executar_sql("SELECT coluna_que_nao_existe FROM dw.orders")
    assert resultado is None
    assert erro is not None
