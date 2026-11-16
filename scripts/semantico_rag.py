"""Agente Semantico/RAG (E5): envelopa tool_busca_vetorial e devolve a lista parseada."""
import json

from tools import tool_busca_vetorial


def buscar_contexto(pergunta: str, k: int = 3) -> list[dict]:
    return json.loads(tool_busca_vetorial(pergunta, k))
