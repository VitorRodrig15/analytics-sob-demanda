"""Entregável 4.3 (E4) - Definição das tools/functions do agente.

Duas ferramentas de verdade, cada uma resolvendo uma parte do que o
Agente Semântico/RAG e o Agente de Execução (desenhados na E1) fazem:

  busca_vetorial  - consulta o schema rag (o dicionário). Reusa o retrieve()
                    que já existe desde o 3.1, sem reescrever nada.
  consulta_banco  - roda um SELECT de verdade contra o schema dw, pela
                    PRIMEIRA vez no projeto. Usa a role agente_leitura
                    (sql/agent_readonly_role.sql), criada antes desta
                    ferramenta existir de propósito: mesmo que o agente
                    "decida" algo além de SELECT, é o PostgreSQL quem
                    recusa - a validação aqui dentro é só uma primeira
                    camada, não substitui o Agente Validador da E5.

Decidi NÃO criar uma terceira tool "formata_resposta": formatar a resposta
final é só a mensagem de texto comum que a LLM escreve depois de ter o que
precisa - não existe nenhum código a executar ali, então vira tool call
seria uma complicação sem necessidade.

Uso (de outro script):
    from tools import TOOLS, execute_tool
    resultado_json = execute_tool("busca_vetorial", {"pergunta": "..."})
"""
import json
import os
import re
import time
from urllib.parse import urlsplit, urlunsplit

import psycopg

from search import retrieve

MAX_ROWS = 50          # nenhuma consulta devolve mais que isso pro agente
STATEMENT_CHARS = 4000  # limite de tamanho do SQL que aceitamos ler

# Palavras que bloqueiam a consulta aqui mesmo, antes de chegar no banco -
# defesa em profundidade. A trava que realmente importa é a role
# agente_leitura (read-only de verdade), não esta lista.
FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|GRANT|REVOKE|CREATE|CALL|COPY)\b",
    re.IGNORECASE,
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "busca_vetorial",
            "description": (
                "Busca no dicionário semântico (métricas, regras de negócio, "
                "descrições de tabela e exemplos de SQL validados) os trechos "
                "mais relevantes para uma pergunta. Use sempre antes de "
                "escrever uma consulta SQL, para saber a fórmula e as regras "
                "corretas - nunca invente uma fórmula de memória."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pergunta": {"type": "string", "description": "A pergunta ou termo a buscar"},
                    "k": {"type": "integer", "description": "Quantos resultados trazer (padrão 3)"},
                },
                "required": ["pergunta"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consulta_banco",
            "description": (
                "Executa uma consulta SELECT de leitura no schema dw (dados "
                "de negócio: pedidos, clientes, vendedores, produtos, "
                "pagamentos, avaliações). Use só depois de buscar a fórmula "
                "e as regras no busca_vetorial. Só SELECT é permitido; "
                "qualquer outro comando é recusado pelo banco."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "A consulta SELECT completa, no schema dw"},
                },
                "required": ["sql"],
            },
        },
    },
]


def agent_database_url() -> str:
    """Monta a connection string do usuario agente_leitura, reaproveitando
    host/porta/banco de DATABASE_URL e trocando so o usuario e a senha."""
    base = os.getenv("DATABASE_URL", "postgresql://analytics:analytics@localhost:5432/analytics")
    base = base.replace("postgresql+psycopg://", "postgresql://")
    parts = urlsplit(base)
    user = os.environ["AGENT_DB_USER"]
    password = os.environ["AGENT_DB_PASSWORD"]
    netloc = f"{user}:{password}@{parts.hostname}:{parts.port or 5432}"
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))


def tool_busca_vetorial(pergunta: str, k: int = 3) -> str:
    # O embedding em si e rapido (~1-2s), mas a API da NVIDIA as vezes
    # devolve um erro 500 transitorio (visto na pratica). Uma retentativa
    # curta resolve a maioria dos casos sem gastar uma rodada inteira do
    # agente (~150s) so por causa de um erro passageiro.
    try:
        chunks = retrieve(pergunta, k=k)
    except Exception:
        time.sleep(2)
        chunks = retrieve(pergunta, k=k)
    return json.dumps(
        [{"fonte": c.title, "tipo": c.doc_type, "similaridade": round(c.similarity, 3),
          "conteudo": c.content} for c in chunks],
        ensure_ascii=False,
    )


def tool_consulta_banco(sql: str) -> str:
    sql = sql.strip().rstrip(";")

    if len(sql) > STATEMENT_CHARS:
        return json.dumps({"erro": "consulta muito longa"})
    if ";" in sql:
        return json.dumps({"erro": "apenas uma instrução por chamada"})
    if not re.match(r"^\s*(SELECT|WITH)\b", sql, re.IGNORECASE):
        return json.dumps({"erro": "só consultas SELECT (ou WITH ... SELECT) são permitidas"})
    if FORBIDDEN.search(sql):
        return json.dumps({"erro": "comando não permitido - só leitura"})
    if not re.search(r"\bdw\.\w+", sql):
        return json.dumps({"erro": "a consulta precisa referenciar uma tabela do schema dw (ex.: dw.orders)"})

    try:
        with psycopg.connect(agent_database_url()) as conn:
            conn.read_only = True
            with conn.cursor() as cur:
                cur.execute(f"SELECT * FROM ({sql}) AS consulta LIMIT {MAX_ROWS}")
                columns = [d.name for d in cur.description]
                rows = cur.fetchall()
    except psycopg.Error as exc:
        # Devolve o erro pro agente poder corrigir sozinho (mesmo principio
        # do loop de correcao da arquitetura da E1), sem derrubar o script.
        return json.dumps({"erro": str(exc).splitlines()[0]})

    return json.dumps(
        {"colunas": columns, "linhas": [dict(zip(columns, row)) for row in rows],
         "total_retornado": len(rows)},
        ensure_ascii=False, default=str,
    )


def execute_tool(name: str, arguments: dict) -> str:
    """Despacha para a função certa a partir do nome que a LLM pediu.

    Qualquer exceção (erro transitório da API da NVIDIA, timeout, etc.) é
    pega aqui e vira um JSON de erro, nunca derruba o loop do agente - uma
    ferramenta falhar deve ser algo que o agente consegue ver e reagir,
    igual já fazíamos com erro de SQL, não um crash do processo inteiro.
    """
    try:
        if name == "busca_vetorial":
            return tool_busca_vetorial(arguments["pergunta"], arguments.get("k", 3))
        if name == "consulta_banco":
            return tool_consulta_banco(arguments["sql"])
        return json.dumps({"erro": f"ferramenta desconhecida: {name}"})
    except Exception as exc:
        return json.dumps({"erro": f"falha ao executar {name}: {exc}"})
