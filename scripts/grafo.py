"""Entregável 5 (E5) - O grafo (itens 5.2 e 5.3).

Último passo da arquitetura multiagente: liga os 5 agentes já construídos e
testados isoladamente (Tasks 4-7) num `StateGraph` do LangGraph, usando as
funções de roteamento puras da Task 3 (scripts/grafo_routing.py) como
arestas condicionais. Este módulo não contém nenhuma lógica de negócio nova
- só orquestra quem já existe.

Formato do grafo (docs/entregas/E5/design.md):
    orquestrador --esclarecimento--> execucao_resposta --> END
    orquestrador --com_contexto--> semantico_rag
    semantico_rag --definicao--> execucao_resposta --> END
    semantico_rag --gerar_sql--> gerador_sql
    gerador_sql --> validador
    validador --executar--> execucao_resposta
    validador --tentar_de_novo--> gerador_sql
    validador --esgotado--> execucao_resposta
    execucao_resposta --tentar_de_novo--> gerador_sql (erro real de execução)
    execucao_resposta --ok/esgotado--> END

Uso como módulo:
    from grafo import run_grafo
    ctx = run_grafo("qual foi a receita de 2017?")

Uso como CLI (dentro do container):
    docker compose exec app python scripts/grafo.py "qual foi a receita de 2017?"
"""
import argparse
import os

from langgraph.graph import END, StateGraph
from openai import OpenAI

from execucao_resposta import executar_sql, responder
from gerador_sql import gerar_sql
from grafo_routing import (
    rotear_apos_execucao,
    rotear_apos_orquestrador,
    rotear_apos_semantico,
    rotear_apos_validador,
)
from orquestrador import classificar_intencao
from semantico_rag import buscar_contexto
from state import AgentContext
from validador import validar_sql

NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")

# Nota sobre o "State type" do StateGraph: a versão instalada (langgraph
# 1.2.19) aceita uma dataclass comum (AgentContext) como schema do
# StateGraph diretamente - confirmado rodando um grafo de 1 nó e inspecionando
# o tipo recebido dentro do nó (state.AgentContext, não um dict e não um
# TypedDict). Não foi preciso criar um TypedDict espelhando os campos.
# Detalhe que importa pro resto do módulo: cada nó RECEBE uma instância real
# de AgentContext (pode chamar ctx.registrar(...) normalmente), mas o
# `.invoke()` do grafo compilado DEVOLVE um dict simples (não uma
# AgentContext) - por isso run_grafo() reconstrói a dataclass no final.


def no_orquestrador(ctx: AgentContext, client: OpenAI) -> AgentContext:
    ctx.intencao = classificar_intencao(ctx.pergunta, client)
    ctx.registrar(f"orquestrador: classificou a intencao como '{ctx.intencao}'")
    return ctx


def no_semantico_rag(ctx: AgentContext) -> AgentContext:
    ctx.contexto_rag = buscar_contexto(ctx.pergunta)
    ctx.registrar(
        f"semantico_rag: buscou {len(ctx.contexto_rag)} trecho(s) de contexto"
    )
    return ctx


def no_gerador_sql(ctx: AgentContext, client: OpenAI) -> AgentContext:
    # Motivo do erro da tentativa anterior (se houver), para o gerador
    # corrigir - prioriza o erro de execucao (mais recente/especifico) e cai
    # para o motivo de rejeicao do validador, mesma precedencia usada em
    # execucao_resposta._montar_user_content.
    erro_anterior = ctx.erro_execucao or ctx.motivo_rejeicao

    # Limpa o estado da tentativa anterior ANTES de gerar o novo SQL - sem
    # isso, validacao_ok/motivo_rejeicao/erro_execucao de uma tentativa
    # anterior vazam pro roteamento do proximo passo (validador ou execucao)
    # ou pra logica de mensagem de responder().
    ctx.validacao_ok = None
    ctx.motivo_rejeicao = None
    ctx.erro_execucao = None

    ctx.sql_gerado = gerar_sql(ctx.pergunta, ctx.contexto_rag, erro_anterior, client)
    ctx.registrar(f"gerador_sql: gerou SQL (tentativa {ctx.tentativas + 1})")
    return ctx


def no_validador(ctx: AgentContext) -> AgentContext:
    resultado = validar_sql(ctx.sql_gerado or "")
    ctx.validacao_ok = resultado.ok
    if resultado.ok:
        ctx.registrar("validador: SQL aprovado")
    else:
        ctx.motivo_rejeicao = resultado.motivo
        # Incrementa tentativas no momento exato em que marca
        # validacao_ok = False - e esse valor que rotear_apos_validador le
        # logo depois, pra decidir "tentar_de_novo" ou "esgotado".
        ctx.tentativas += 1
        ctx.registrar(
            f"validador: SQL rejeitado ({resultado.motivo}) - tentativa {ctx.tentativas}"
        )
    return ctx


def no_execucao_resposta(ctx: AgentContext, client: OpenAI) -> AgentContext:
    # So executa o SQL se houver um SQL aprovado pelo validador esperando
    # execucao (ctx.validacao_ok is True) e ainda nao tentado nesta
    # passagem. ctx.erro_execucao is None faz parte dessa guarda por um
    # motivo especifico: quando rotear_apos_execucao devolve "esgotado" (ver
    # _rotear_apos_execucao_resposta), a aresta condicional reentra neste
    # mesmo no "execucao_resposta" (self-loop) em vez de voltar pro
    # gerador_sql - nesse caso ctx.erro_execucao ainda esta preenchido com o
    # erro da ultima tentativa (so o gerador_sql limpa esse campo, e nao
    # passamos por ele no caminho esgotado), e por isso cai direto pra
    # responder() com esse erro, sem tentar executar de novo o mesmo SQL
    # que ja falhou e esgotou as tentativas.
    if (
        ctx.validacao_ok is True
        and ctx.resultado_execucao is None
        and ctx.erro_execucao is None
    ):
        resultado, erro = executar_sql(ctx.sql_gerado or "")
        if erro is None:
            ctx.resultado_execucao = resultado
            total = resultado.get("total_retornado") if resultado else 0
            ctx.registrar(f"execucao_resposta: SQL executado, {total} linha(s)")
        else:
            # Incrementa tentativas no momento exato em que marca
            # erro_execucao - e esse valor que rotear_apos_execucao le logo
            # depois.
            ctx.erro_execucao = erro
            ctx.tentativas += 1
            ctx.registrar(
                f"execucao_resposta: erro ao executar SQL ({erro}) - tentativa {ctx.tentativas}"
            )
            return ctx

    ctx.resposta_final = responder(ctx, client)
    ctx.registrar("execucao_resposta: resposta final gerada")
    return ctx


def _rotear_apos_execucao_resposta(ctx: AgentContext) -> str:
    """Decide se execucao_resposta encerra o grafo (END) ou volta pro
    gerador_sql.

    So se baseia em ctx.resposta_final (nao em ctx.erro_execucao) porque o
    caminho "esgotado" reentra no proprio no execucao_resposta (self-loop,
    ver no_execucao_resposta) deixando ctx.erro_execucao preenchido mesmo
    DEPOIS de ja ter escrito a resposta final de falha nessa segunda
    passagem - se checassemos erro_execucao aqui, esse caso ficaria votando
    "esgotado" pra sempre (bug de loop infinito encontrado rodando a fiacao
    do grafo com stubs antes do run real). resposta_final so fica vazio
    enquanto o no ainda nao chamou responder() - ou seja, exatamente quando
    acabou de rodar o SQL nesta passagem e bateu um erro real."""
    if ctx.resposta_final:
        return "fim"
    return rotear_apos_execucao(ctx)


def montar_grafo():
    """Monta e compila o StateGraph com os 5 agentes e o loop de correcao.

    O client da OpenAI/NVIDIA e construido uma unica vez aqui e injetado via
    closure nos nos que precisam de LLM (orquestrador, gerador_sql,
    execucao_resposta) - nao criamos um client novo a cada chamada de no."""
    client = OpenAI(base_url=NVIDIA_BASE_URL, api_key=os.environ["NVIDIA_API_KEY"])

    grafo = StateGraph(AgentContext)

    grafo.add_node("orquestrador", lambda ctx: no_orquestrador(ctx, client))
    grafo.add_node("semantico_rag", no_semantico_rag)
    grafo.add_node("gerador_sql", lambda ctx: no_gerador_sql(ctx, client))
    grafo.add_node("validador", no_validador)
    grafo.add_node("execucao_resposta", lambda ctx: no_execucao_resposta(ctx, client))

    grafo.set_entry_point("orquestrador")

    grafo.add_conditional_edges(
        "orquestrador",
        rotear_apos_orquestrador,
        {"esclarecimento": "execucao_resposta", "com_contexto": "semantico_rag"},
    )
    grafo.add_conditional_edges(
        "semantico_rag",
        rotear_apos_semantico,
        {"definicao": "execucao_resposta", "gerar_sql": "gerador_sql"},
    )
    grafo.add_edge("gerador_sql", "validador")
    grafo.add_conditional_edges(
        "validador",
        rotear_apos_validador,
        {
            "executar": "execucao_resposta",
            "tentar_de_novo": "gerador_sql",
            "esgotado": "execucao_resposta",
        },
    )
    grafo.add_conditional_edges(
        "execucao_resposta",
        _rotear_apos_execucao_resposta,
        {"tentar_de_novo": "gerador_sql", "esgotado": "execucao_resposta", "fim": END},
    )

    return grafo.compile()


def run_grafo(pergunta: str, verbose: bool = False) -> AgentContext:
    """Roda o grafo completo para uma pergunta e devolve o AgentContext
    final (reconstruido a partir do dict que .invoke() devolve - ver nota no
    topo do modulo sobre o State type do StateGraph)."""
    compilado = montar_grafo()
    estado_inicial = AgentContext(pergunta=pergunta)

    # recursion_limit alto o bastante pra cobrir o loop de correcao
    # (gerador_sql -> validador -> execucao_resposta -> gerador_sql, ate
    # MAX_TENTATIVAS=3 vezes) sem bater no limite padrao do LangGraph.
    # verbose nao altera nada aqui: a impressao passo a passo (main()) e
    # feita depois, lendo ctx.historico, porque os nos ja rodam de forma
    # sincrona dentro de .invoke() - nao ha progresso incremental pra
    # mostrar durante a chamada.
    resultado_dict = compilado.invoke(estado_inicial, config={"recursion_limit": 50})

    return AgentContext(**resultado_dict)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pergunta")
    args = parser.parse_args()

    print(f'Pergunta: "{args.pergunta}"\n')
    ctx = run_grafo(args.pergunta, verbose=True)

    print("Historico:")
    for evento in ctx.historico:
        print(f"  - {evento}")

    print(f"\nResposta final:\n{ctx.resposta_final}")


if __name__ == "__main__":
    main()
