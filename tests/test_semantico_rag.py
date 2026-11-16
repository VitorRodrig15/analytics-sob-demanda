# tests/test_semantico_rag.py
from unittest.mock import patch
from scripts.semantico_rag import buscar_contexto

def test_buscar_contexto_parseia_json_da_tool():
    fake_json = '[{"fonte": "Ticket medio", "tipo": "metrica", "similaridade": 0.9, "conteudo": "..."}]'
    with patch("scripts.semantico_rag.tool_busca_vetorial", return_value=fake_json) as mocked:
        resultado = buscar_contexto("qual o ticket medio?", k=3)
    mocked.assert_called_once_with("qual o ticket medio?", 3)
    assert resultado == [{"fonte": "Ticket medio", "tipo": "metrica", "similaridade": 0.9, "conteudo": "..."}]
