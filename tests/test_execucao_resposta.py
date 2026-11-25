# tests/test_execucao_resposta.py
from execucao_resposta import _montar_user_content, executar_sql
from state import AgentContext


def test_montar_user_content_fora_de_escopo_nao_tenta_responder():
    ctx = AgentContext(
        pergunta="me passa a receita de um bolo de maracuja",
        intencao="fora_de_escopo",
    )
    conteudo = _montar_user_content(ctx)
    assert "não tem relação" in conteudo
    assert "não tente responder" in conteudo


def test_executar_sql_sucesso():
    resultado, erro = executar_sql("SELECT COUNT(*) AS total FROM dw.orders")
    assert erro is None
    assert resultado["total_retornado"] == 1
    assert resultado["linhas"][0]["total"] > 0


def test_executar_sql_erro_de_sintaxe_nao_derruba_processo():
    resultado, erro = executar_sql("SELECT coluna_que_nao_existe FROM dw.orders")
    assert resultado is None
    assert erro is not None
