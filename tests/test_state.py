# tests/test_state.py
from state import AgentContext

def test_agent_context_defaults():
    ctx = AgentContext(pergunta="qual a receita de 2017?")
    assert ctx.pergunta == "qual a receita de 2017?"
    assert ctx.intencao is None
    assert ctx.contexto_rag == []
    assert ctx.tentativas == 0
    assert ctx.historico == []

def test_agent_context_registrar_evento():
    ctx = AgentContext(pergunta="x")
    ctx.registrar("orquestrador: intencao=dado")
    ctx.registrar("gerador_sql: sql gerado")
    assert ctx.historico == ["orquestrador: intencao=dado", "gerador_sql: sql gerado"]
