"""Entregável 5 (E5) - Prova de que os 3 agentes com LLM funcionam isolados (5.1).

O Validador (scripts/validador.py, Task 2) e o Agente Semântico/RAG
(scripts/semantico_rag.py, Task 4) já ficaram comprovados "testáveis sozinhos"
pelas baterias das Tasks 2 e 4. Faltam os outros 3 agentes que chamam a LLM:
Orquestrador (Task 5, classifica a intenção), Gerador de SQL (Task 6, escreve
o SELECT) e Execução/Resposta (Task 7, roda o SQL e escreve a resposta final).
Este script chama cada um deles isoladamente, com casos escolhidos pra cobrir
os comportamentos que o prompt de cada agente promete, e grava um relatório
Markdown com pergunta/entrada, saída real e uma avaliação ✅/❌ por caso -
mesmo padrão textual do relatório da E4 (docs/e4_testes_agente.md).

Roda 7 chamadas reais de LLM (nenhum mock) - cada uma leva uns 130-180s no
gpt-oss-20b via NVIDIA NIM, então a bateria toda leva uns 15-25 minutos.

Uso (dentro do container):
    docker compose exec app python scripts/testar_agentes_individuais.py
"""
import os
import time
from pathlib import Path

from openai import OpenAI

from execucao_resposta import executar_sql, responder
from gerador_sql import gerar_sql
from orquestrador import NVIDIA_BASE_URL, classificar_intencao
from semantico_rag import buscar_contexto
from state import AgentContext

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "e5_testes_agentes_individuais.md"


def main() -> None:
    client = OpenAI(base_url=NVIDIA_BASE_URL, api_key=os.environ["NVIDIA_API_KEY"])
    inicio = time.perf_counter()
    casos: list[dict] = []

    # --- 1) Orquestrador: classificar_intencao, 3 perguntas, uma de cada categoria ---
    perguntas_orquestrador = [
        ("definicao", "O que é ticket médio?"),
        ("dado", "Qual foi a receita total de 2017?"),
        ("esclarecimento", "me fala dos vendedores"),
    ]
    for i, (categoria_esperada, pergunta) in enumerate(perguntas_orquestrador, 1):
        print(f"[orquestrador {i}/3] esperado={categoria_esperada}: {pergunta}")
        categoria = classificar_intencao(pergunta, client)
        print(f"   -> {categoria}")
        casos.append({
            "agente": "Orquestrador (classificar_intencao)",
            "titulo": f"Caso O{i}: {categoria_esperada}",
            "entrada": f"pergunta = {pergunta!r}",
            "esperado": categoria_esperada,
            "saida": categoria,
        })

    # --- 2) Gerador de SQL: gerar_sql, 2 chamadas (sem erro / com erro_anterior) ---
    pergunta_sql = "Qual foi a receita total de 2017?"
    contexto_rag_sql = buscar_contexto(pergunta_sql)

    print(f"[gerador_sql 1/2] sem erro_anterior: {pergunta_sql}")
    sql_1 = gerar_sql(pergunta_sql, contexto_rag_sql, None, client)
    print(f"   -> {sql_1[:120]}...")
    casos.append({
        "agente": "Gerador de SQL (gerar_sql)",
        "titulo": "Caso G1: sem erro_anterior",
        "entrada": (
            f"pergunta = {pergunta_sql!r}\n"
            f"contexto_rag = {len(contexto_rag_sql)} chunk(s) de {[c.get('fonte') for c in contexto_rag_sql]}\n"
            "erro_anterior = None"
        ),
        "saida": sql_1,
    })

    erro_anterior = 'column "orders.customer_city" does not exist'
    print(f"[gerador_sql 2/2] com erro_anterior: {erro_anterior!r}")
    sql_2 = gerar_sql(pergunta_sql, contexto_rag_sql, erro_anterior, client)
    print(f"   -> {sql_2[:120]}...")
    casos.append({
        "agente": "Gerador de SQL (gerar_sql)",
        "titulo": "Caso G2: com erro_anterior",
        "entrada": (
            f"pergunta = {pergunta_sql!r}\n"
            f"contexto_rag = {len(contexto_rag_sql)} chunk(s) de {[c.get('fonte') for c in contexto_rag_sql]}\n"
            f"erro_anterior = {erro_anterior!r}"
        ),
        "saida": sql_2,
    })

    # --- 3) Execução/Resposta: responder, 2 chamadas (resultado real / 0 linhas) ---
    print("[execucao_resposta 1/2] responder com resultado real do banco")
    sql_contagem = "SELECT COUNT(*) AS total_pedidos FROM dw.orders"
    resultado_real, erro_exec = executar_sql(sql_contagem)
    print(f"   -> executar_sql: resultado={resultado_real}, erro={erro_exec}")
    ctx_real = AgentContext(
        pergunta="Quantos pedidos existem na base?",
        intencao="dado",
        contexto_rag=[],
        sql_gerado=sql_contagem,
        resultado_execucao=resultado_real,
    )
    resposta_real = responder(ctx_real, client)
    print(f"   -> {resposta_real[:120]}...")
    casos.append({
        "agente": "Execução e Resposta (responder)",
        "titulo": "Caso R1: resultado real (linhas não vazias)",
        "entrada": (
            f"ctx.pergunta = {ctx_real.pergunta!r}\n"
            f"ctx.intencao = {ctx_real.intencao!r}\n"
            f"ctx.sql_gerado = {sql_contagem!r}\n"
            f"ctx.resultado_execucao (via executar_sql real) = {resultado_real}"
        ),
        "saida": resposta_real,
    })

    print("[execucao_resposta 2/2] responder com resultado_execucao['linhas'] == []")
    ctx_vazio = AgentContext(
        pergunta="Qual foi a receita de vendas de produtos na categoria 'inexistente_xyz' em 2018?",
        intencao="dado",
        contexto_rag=[],
        sql_gerado=(
            "SELECT SUM(price) AS receita FROM dw.order_items oi "
            "JOIN dw.products p ON p.product_id = oi.product_id "
            "WHERE p.product_category = 'inexistente_xyz'"
        ),
        resultado_execucao={"colunas": ["receita"], "linhas": [], "total_retornado": 0},
    )
    resposta_vazia = responder(ctx_vazio, client)
    print(f"   -> {resposta_vazia[:120]}...")
    casos.append({
        "agente": "Execução e Resposta (responder)",
        "titulo": "Caso R2: resultado_execucao['linhas'] == []",
        "entrada": (
            f"ctx.pergunta = {ctx_vazio.pergunta!r}\n"
            f"ctx.intencao = {ctx_vazio.intencao!r}\n"
            f"ctx.sql_gerado = {ctx_vazio.sql_gerado!r}\n"
            f"ctx.resultado_execucao (sintético) = {ctx_vazio.resultado_execucao}"
        ),
        "saida": resposta_vazia,
    })

    total = time.perf_counter() - inicio
    print(f"\n{len(casos)} casos rodados em {total / 60:.1f} min")

    escrever_relatorio(casos, total)
    print(f"Relatório salvo em {OUTPUT.relative_to(ROOT)}")


def escrever_relatorio(casos: list[dict], total_segundos: float) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    linhas = [
        "# 5.1 - Prova de que os 3 agentes com LLM funcionam isolados",
        "",
        "7 chamadas reais de LLM (NVIDIA NIM, gpt-oss-20b) contra os 3 agentes que ainda "
        "não tinham sido comprovados \"testáveis sozinhos\" pelas Tasks anteriores: "
        "Orquestrador (3 casos), Gerador de SQL (2 casos) e Execução e Resposta (2 casos). "
        "O Validador (Task 2) e o Agente Semântico/RAG (Task 4) já ficaram comprovados "
        "pelas baterias daquelas tasks.",
        "",
        f"Bateria completa rodada em {total_segundos / 60:.1f} min.",
        "",
        "Avaliação (✅/❌/⚠️) é um primeiro julgamento de quem rodou o script - a "
        "correção final de julgamento humano é do responsável pela E5, mesmo padrão "
        "das entregas anteriores.",
        "",
    ]

    for caso in casos:
        linhas.append(f"## {caso['titulo']} - {caso['agente']}")
        linhas.append("")
        linhas.append("**Entrada:**")
        linhas.append("```")
        linhas.append(caso["entrada"])
        linhas.append("```")
        linhas.append("")
        if "esperado" in caso:
            linhas.append(f"**Categoria esperada:** {caso['esperado']}")
            linhas.append("")
        linhas.append("**Saída real:**")
        linhas.append("```")
        linhas.append(caso["saida"])
        linhas.append("```")
        linhas.append("")
        linhas.append("**Avaliação:** _(preencher ✅/❌)_")
        linhas.append("")

    OUTPUT.write_text("\n".join(linhas), encoding="utf-8")


if __name__ == "__main__":
    main()
