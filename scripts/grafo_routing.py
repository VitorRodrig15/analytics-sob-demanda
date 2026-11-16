"""Funcoes de roteamento do grafo (arestas condicionais) do sistema multiagente (E5).

Cada funcao recebe o AgentContext e devolve o nome da proxima aresta.
Sem LLM, sem banco, sem rede.
"""

from scripts.state import AgentContext

MAX_TENTATIVAS = 3


def rotear_apos_orquestrador(ctx: AgentContext) -> str:
    if ctx.intencao == "esclarecimento":
        return "esclarecimento"
    return "com_contexto"


def rotear_apos_semantico(ctx: AgentContext) -> str:
    if ctx.intencao == "definicao":
        return "definicao"
    return "gerar_sql"


def rotear_apos_validador(ctx: AgentContext) -> str:
    if ctx.validacao_ok is True:
        return "executar"
    if ctx.tentativas < MAX_TENTATIVAS:
        return "tentar_de_novo"
    return "esgotado"


def rotear_apos_execucao(ctx: AgentContext) -> str:
    if ctx.erro_execucao is None:
        return "ok"
    if ctx.tentativas < MAX_TENTATIVAS:
        return "tentar_de_novo"
    return "esgotado"
