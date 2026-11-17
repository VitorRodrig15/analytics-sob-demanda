"""Entregável 5 (E5) - Bateria de testes de integração do grafo completo (5.4/5.5).

Diferente das baterias anteriores (E3 3.5, E4 4.4, que testavam um agente
isolado), aqui o que se testa é a orquestração: os 5 agentes ligados pelo
`StateGraph` de `scripts/grafo.py`, incluindo os dois loops de correção
(Validador -> Gerador de SQL, e Execução -> Gerador de SQL) e os dois casos
de borda que encerram sem travar (tentativas esgotadas, consulta sem
resultado).

7 cenários, escolhidos para cobrir cada aresta do grafo pelo menos uma vez:
  1. caminho feliz com dado real (dicionário + banco, sem erro)
  2. definição pura (pula Gerador de SQL e execução)
  3. pergunta ambígua (esclarecimento, não consulta nada)
  4. Validador rejeita na 1a tentativa, aprova na 2a (loop de correção do validador)
  5. execução falha na 1a tentativa (erro real do Postgres), corrige na 2a
  6. tentativas esgotadas (métrica indisponível, sem tabela/coluna real possível)
  7. consulta válida mas sem linhas (período fora dos dados)

LATÊNCIA: cada cenário chama a LLM de 3 a 9 vezes (orquestrador + possíveis
voltas de gerador_sql/validador/execução), ~130-180s por chamada - a bateria
toda pode levar mais de 1h. Roda em segundo plano, salvando cada resultado
assim que fica pronto (mesmo padrão de scripts/run_agent_tests.py da E4).

Os cenários 4, 5 e 6 dependem de o LLM *de fato* errar na primeira tentativa
- não há mock nem forçar resultado (regra do projeto: nunca mockar a LLM).
As perguntas foram desenhadas pra tornar o erro provável (tabela fora do
schema dw, coluna que não existe, métrica sem tabela correspondente), mas o
resultado real pode variar entre execuções; isso é avaliado manualmente
depois, lendo o historico de cada cenário.

Uso (dentro do container):
    docker compose exec app python scripts/run_e5_tests.py
"""
import json
import time
from dataclasses import asdict
from pathlib import Path

from grafo import run_grafo

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "e5_testes_integracao.jsonl"

# (id, categoria, pergunta, o que o cenario tenta provar)
CENARIOS = [
    (1, "caminho_feliz",
     "Qual foi a receita de 2017?",
     "dado real, sem erro - caminho orquestrador->semantico_rag->gerador_sql->validador->execucao"),
    (2, "definicao",
     "O que é ticket médio?",
     "pula gerador_sql e execucao - so dicionario semantico"),
    (3, "ambigua",
     "Como estamos?",
     "cai em esclarecimento, termina sem consultar nada"),
    (4, "loop_validador",
     "Compare a receita por vendedor em cada região no último trimestre "
     "com o trimestre anterior, detalhando também o frete médio por pedido.",
     "pergunta complexa (multi-CTE/multi-tabela) para tentar induzir SQL "
     "que referencie alguma tabela sem o prefixo do schema dw na 1a "
     "tentativa, e ser rejeitada pelo Validador - corrigindo na 2a"),
    (5, "loop_execucao",
     "Quais são os nomes dos clientes que mais compraram em 2018?",
     "dw.customers não tem coluna de nome (so vendedores/clientes sao "
     "identificados por id/cidade/uf) - tenta induzir o gerador_sql a "
     "inventar uma coluna que nao existe, causando erro real do Postgres "
     "na execucao (nao pego pelo Validador, que só olha tabela/schema)"),
    (6, "esgotado",
     "Qual foi a margem de lucro líquida por categoria de produto no "
     "último trimestre, considerando o CMV e as despesas de marketing?",
     "margem de lucro líquida é métrica indisponível no dicionário (sem "
     "tabela correspondente) - tenta esgotar as 3 tentativas sem nunca "
     "conseguir um SQL válido e executável"),
    (7, "sem_resultado",
     "Qual foi a receita de pedidos entregues em janeiro de 2016?",
     "SQL válido e executável, mas sem linhas: os dados do dataset só "
     "começam em set/2016 - periodo pedido e anterior ao inicio dos dados"),
]


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    # Trunca o arquivo no inicio de cada execucao da bateria: sem isso, uma
    # nova rodada so acrescentaria registros ao .jsonl ja publicado em vez
    # de substitui-lo, misturando execucoes diferentes no mesmo arquivo de
    # evidencia. Dentro do loop abaixo continuamos abrindo em modo "a"
    # (append), que e o que da a seguranca contra crash/corte no meio de
    # uma bateria longa - so o inicio da bateria toda e que reseta.
    OUTPUT.write_text("", encoding="utf-8")
    inicio = time.perf_counter()

    for cenario_id, categoria, pergunta, objetivo in CENARIOS:
        print(f"[{cenario_id}/{len(CENARIOS)}] {categoria}: {pergunta}")
        t0 = time.perf_counter()
        ctx = run_grafo(pergunta, verbose=True)
        dt = time.perf_counter() - t0

        registro = {
            "cenario_id": cenario_id,
            "categoria": categoria,
            "objetivo": objetivo,
            "duracao_s": round(dt, 1),
            **asdict(ctx),
        }
        # default=str: resultado_execucao pode trazer Decimal/datetime do
        # psycopg (colunas numeric/timestamp), que o json padrao nao
        # serializa - aqui so precisamos do registro legivel no .jsonl, nao
        # de round-trip de tipo.
        with OUTPUT.open("a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False, default=str) + "\n")

        print(f"   -> {ctx.tentativas} tentativa(s), {dt:.0f}s, intencao='{ctx.intencao}'")
        for evento in ctx.historico:
            print(f"      - {evento}")
        print(f"   Resposta final: {ctx.resposta_final[:200]}\n")

    total = time.perf_counter() - inicio
    print(f"{len(CENARIOS)} cenários concluídos em {total / 60:.1f} min")
    print(f"Resultados salvos em {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
