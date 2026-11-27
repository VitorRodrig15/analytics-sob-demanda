"""Validador de SQL deterministico (E5).

Antes de qualquer SQL gerado por um LLM chegar ao banco, passa por aqui:
um parser real (sqlglot) em vez de regex, pra nao ser enganado por coisas
como um ";" dentro de uma string literal ou SQL escondido num comentario.

Regras, nessa ordem:
1. exatamente um statement;
2. o statement (ou o SELECT/UNION/EXCEPT/INTERSECT interno de um WITH) e
   uma leitura pura - nada de INSERT/UPDATE/DELETE/MERGE/CREATE/DROP, nem
   escondido dentro de uma CTE (ex.: `WITH x AS (DELETE FROM ... RETURNING
   *) SELECT * FROM x`), nem um `SELECT ... INTO` (que cria tabela);
3. toda tabela referenciada esta no schema `dw` (o schema `rag`, usado para
   o conhecimento do RAG, nao e dado de negocio e fica de fora), e precisa
   haver pelo menos uma tabela `dw.*` referenciada - uma consulta sem
   nenhuma tabela (ex.: `SELECT 'texto' AS msg`) nao e uma consulta real ao
   banco e nao deve ser narrada como se fosse.
"""

from dataclasses import dataclass

import sqlglot
from sqlglot import exp


@dataclass
class ValidacaoResultado:
    ok: bool
    motivo: str | None = None


def validar_sql(sql: str) -> ValidacaoResultado:
    try:
        statements = sqlglot.parse(sql, read="postgres")
    except sqlglot.errors.ParseError as e:
        return ValidacaoResultado(ok=False, motivo=f"SQL invalido: {e}")

    statements = [s for s in statements if s is not None]

    if len(statements) != 1:
        return ValidacaoResultado(
            ok=False,
            motivo=f"Esperado exatamente 1 instrucao SQL, encontrado {len(statements)}",
        )

    statement = statements[0]

    # Checagem estrutural, nao so "o statement de topo e um Select": um
    # INSERT/UPDATE/DELETE/MERGE/CREATE/DROP pode estar escondido dentro de
    # uma CTE, que o Postgres aceita com RETURNING (ex.: `WITH x AS (DELETE
    # FROM dw.orders RETURNING *) SELECT * FROM x`) - isso nao e um SELECT
    # inofensivo so porque o statement de topo e um exp.Select. Procuramos
    # esses nos em qualquer lugar da arvore, nao so no nivel de topo.
    escrita = statement.find(
        exp.Insert, exp.Update, exp.Delete, exp.Merge, exp.Create, exp.Drop
    )
    if escrita is not None:
        return ValidacaoResultado(
            ok=False,
            motivo=f"Comando de escrita nao permitido: {escrita.sql()}",
        )

    corpo = statement
    if isinstance(corpo, exp.With):
        corpo = corpo.this

    if not isinstance(corpo, (exp.Select, exp.Union, exp.Except, exp.Intersect)):
        return ValidacaoResultado(
            ok=False,
            motivo="Apenas instrucoes SELECT (ou WITH ... SELECT, incluindo "
            "UNION/EXCEPT/INTERSECT) sao permitidas",
        )

    # `SELECT ... INTO nova_tabela FROM ...` nao e leitura: cria uma tabela
    # nova. sqlglot representa isso como um exp.Select com args["into"]
    # preenchido, nao como um exp.Create - por isso essa checagem e
    # separada da busca de exp.Create acima.
    for sel in statement.find_all(exp.Select):
        if sel.args.get("into"):
            return ValidacaoResultado(
                ok=False,
                motivo="SELECT ... INTO nao e permitido (cria tabela)",
            )

    # So as CTEs do WITH de topo (anexado diretamente ao `statement`) contam
    # como "nao e tabela real" - nao usamos find_all(exp.CTE) aqui, porque
    # isso pegaria tambem CTEs definidas dentro de subqueries com escopo
    # proprio (ex.: um IN (WITH orders AS (...) SELECT ...) ou uma derived
    # table), que nao tem relacao com as tabelas referenciadas fora dessa
    # subquery - so porque uma CTE interna se chama "orders" nao quer dizer
    # que um FROM orders no nivel de cima se refere a ela.
    #
    # Dependendo da versao do sqlglot, "WITH t AS (...) SELECT ..." vira ou
    # um no exp.With envolvendo o exp.Select, ou um exp.Select com a clausula
    # WITH anexada em si mesmo (args["with"/"with_"]); cobrimos os dois.
    if isinstance(statement, exp.With):
        with_de_topo = statement
    else:
        with_de_topo = statement.args.get("with") or statement.args.get("with_")

    nomes_cte: set[str] = set()
    if with_de_topo is not None:
        nomes_cte = {cte.alias_or_name for cte in with_de_topo.expressions}

    tabelas_dw = 0
    for tabela in statement.find_all(exp.Table):
        if not tabela.db and tabela.name in nomes_cte:
            # referencia a uma CTE definida no proprio WITH, nao a uma tabela real
            continue
        if tabela.db != "dw":
            return ValidacaoResultado(
                ok=False,
                motivo=f"Tabela '{tabela.sql()}' fora do schema permitido 'dw'",
            )
        tabelas_dw += 1

    if tabelas_dw == 0:
        # Nenhuma tabela real referenciada (ex.: `SELECT 'texto' AS msg` ou
        # `SELECT 5962902.01 AS receita`) nao e uma consulta ao banco de
        # verdade - deixar isso passar faria o Agente de Execucao/Resposta
        # narrar um literal inventado como se fosse "resultado real da
        # consulta ao banco" (ver docs/e5_testes_integracao.md, cenario 6).
        return ValidacaoResultado(
            ok=False,
            motivo="Consulta nao referencia nenhuma tabela do schema 'dw'",
        )

    return ValidacaoResultado(ok=True)
