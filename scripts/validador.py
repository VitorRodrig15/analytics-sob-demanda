"""Validador de SQL deterministico (E5).

Antes de qualquer SQL gerado por um LLM chegar ao banco, passa por aqui:
um parser real (sqlglot) em vez de regex, pra nao ser enganado por coisas
como um ";" dentro de uma string literal ou SQL escondido num comentario.

Regras, nessa ordem:
1. exatamente um statement;
2. o statement (ou o SELECT interno de um WITH) e um exp.Select - nada de
   INSERT/UPDATE/DELETE/DROP/etc;
3. toda tabela referenciada esta no schema `dw` (o schema `rag`, usado para
   o conhecimento do RAG, nao e dado de negocio e fica de fora).
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

    corpo = statement
    if isinstance(corpo, exp.With):
        corpo = corpo.this

    if not isinstance(corpo, exp.Select):
        return ValidacaoResultado(
            ok=False,
            motivo="Apenas instrucoes SELECT (ou WITH ... SELECT) sao permitidas",
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

    for tabela in statement.find_all(exp.Table):
        if not tabela.db and tabela.name in nomes_cte:
            # referencia a uma CTE definida no proprio WITH, nao a uma tabela real
            continue
        if tabela.db != "dw":
            return ValidacaoResultado(
                ok=False,
                motivo=f"Tabela '{tabela.sql()}' fora do schema permitido 'dw'",
            )

    return ValidacaoResultado(ok=True)
