# tests/test_grafo_routing.py
from state import AgentContext
from grafo_routing import (
    rotear_apos_orquestrador, rotear_apos_semantico,
    rotear_apos_validador, rotear_apos_execucao,
)

def test_rotear_apos_orquestrador_esclarecimento():
    ctx = AgentContext(pergunta="x", intencao="esclarecimento")
    assert rotear_apos_orquestrador(ctx) == "esclarecimento"

def test_rotear_apos_orquestrador_segue_fluxo():
    for intencao in ("definicao", "dado", "ambas"):
        ctx = AgentContext(pergunta="x", intencao=intencao)
        assert rotear_apos_orquestrador(ctx) == "com_contexto"

def test_rotear_apos_semantico_definicao_pula_sql():
    ctx = AgentContext(pergunta="x", intencao="definicao")
    assert rotear_apos_semantico(ctx) == "definicao"

def test_rotear_apos_semantico_dado_vai_pro_gerador():
    ctx = AgentContext(pergunta="x", intencao="dado")
    assert rotear_apos_semantico(ctx) == "gerar_sql"

def test_rotear_apos_validador_aprovado():
    ctx = AgentContext(pergunta="x", validacao_ok=True)
    assert rotear_apos_validador(ctx) == "executar"

def test_rotear_apos_validador_reprovado_tenta_de_novo():
    ctx = AgentContext(pergunta="x", validacao_ok=False, tentativas=1)
    assert rotear_apos_validador(ctx) == "tentar_de_novo"

def test_rotear_apos_validador_reprovado_esgota_tentativas():
    ctx = AgentContext(pergunta="x", validacao_ok=False, tentativas=3)
    assert rotear_apos_validador(ctx) == "esgotado"

def test_rotear_apos_execucao_sucesso():
    ctx = AgentContext(pergunta="x", erro_execucao=None)
    assert rotear_apos_execucao(ctx) == "ok"

def test_rotear_apos_execucao_erro_tenta_de_novo():
    ctx = AgentContext(pergunta="x", erro_execucao="coluna invalida", tentativas=2)
    assert rotear_apos_execucao(ctx) == "tentar_de_novo"

def test_rotear_apos_execucao_erro_esgota_tentativas():
    ctx = AgentContext(pergunta="x", erro_execucao="coluna invalida", tentativas=3)
    assert rotear_apos_execucao(ctx) == "esgotado"
