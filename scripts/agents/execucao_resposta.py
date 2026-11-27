"""Entregável 5 (E5) - Agente de Execução e Resposta.

Último agente da arquitetura: depois que o Validador (Task 2) aprovou o SQL
escrito pelo Gerador (Task anterior), alguém precisa de fato rodar a
consulta no banco e, com o resultado (ou com o que deu errado), escrever a
resposta final em português para o gestor. São essas as duas
responsabilidades deste módulo, cada uma numa função:

  executar_sql - roda o SELECT de verdade contra o schema dw. Reaproveita a
                 mesma lógica de conexão de tool_consulta_banco
                 (scripts/tools/tools.py): role agente_leitura, conn.read_only =
                 True, LIMIT 50. Não repete as 5 checagens de texto de
                 tool_consulta_banco (não precisar chegar nem perto de
                 DROP/INSERT/etc.) porque isso já é trabalho do Validador
                 (scripts/agents/validador.py, Task 2) - um parser real (sqlglot),
                 que já rodou antes do SQL chegar aqui. Função sem LLM.

  responder    - LLM que escreve a resposta final, ramificando por
                 ctx.intencao / ctx.resultado_execucao / ctx.tentativas:
                 dado real (resultado_execucao), definição pura (só
                 contexto_rag), pedido de esclarecimento, ou falha depois
                 de esgotar as tentativas.

Uso como módulo:
    from openai import OpenAI
    from state import AgentContext
    from execucao_resposta import executar_sql, responder
    resultado, erro = executar_sql("SELECT COUNT(*) AS total FROM dw.orders")
"""
import os

import psycopg
from openai import OpenAI

from prompt_base import PERFIL_VORTEX
from state import AgentContext
from tools import agent_database_url

MAX_ROWS = 50  # mesmo limite de tool_consulta_banco (scripts/tools/tools.py)

LLM_MODEL = os.getenv("LLM_MODEL", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
# 500, não um valor curto: mesmo artefato visto em agent.py (E4),
# orquestrador.py e gerador_sql.py (E5) - a LLM gasta tokens no
# canal de raciocínio interno antes do conteúdo final (era o gpt-oss-20b,
# descontinuado em 18/11/2026; hoje é o
# nvidia/nemotron-3-nano-omni-30b-a3b-reasoning - ver addendum no README
# da E5). Aqui a resposta é um
# texto narrativo em português (não uma palavra nem uma query), então
# precisa de folga parecida com a do gerador_sql.py (700) para a parte
# visível não truncar - 500 cobre uma resposta de algumas frases com sobra.
MAX_TOKENS = 500
TEMPERATURE = 0.3

RESPOSTA_SYSTEM_PROMPT = f"""\
## Perfil
{PERFIL_VORTEX}

## Atribuições
Você é o Agente de Execução e Resposta: o último agente da arquitetura, o \
único que fala diretamente com o gestor. Você recebe a pergunta original e \
o material que outros agentes já reuniram para responder (contexto do \
dicionário semântico, resultado de uma consulta ao banco, ou o motivo de \
uma falha) - você só formata a resposta final em linguagem natural, nunca \
executa nada nem busca nada sozinho.

## Como fazer
Regras que você deve seguir sempre:
1. Responda sempre em português, em tom direto e profissional.
2. Quando usar algo do contexto do dicionário semântico (definição, \
fórmula, regra de negócio), cite a fonte pelo nome.
3. Quando o resultado de uma consulta ao banco vier vazio (zero linhas), \
diga claramente que não foram encontrados resultados - nunca invente um \
número ou afirme que algo não existe além do que o resultado mostra.
4. Nunca invente um número, uma fórmula ou um fato que não esteja no \
material recebido.\
"""


def executar_sql(sql: str) -> tuple[dict | None, str | None]:
    """Roda o SELECT já validado contra o schema dw, pela role de leitura.

    Mesma lógica de conexão de tool_consulta_banco (scripts/tools/tools.py):
    conecta como agente_leitura, conn.read_only = True e envolve a consulta
    num LIMIT 50 - sem as 5 checagens de texto daquela função, porque o SQL
    que chega aqui já passou pelo Validador (scripts/agents/validador.py).
    """
    sql = sql.strip().rstrip(";")

    try:
        with psycopg.connect(agent_database_url()) as conn:
            conn.read_only = True
            with conn.cursor() as cur:
                # Quebra de linha antes do ")" de fechamento: se `sql`
                # terminar com um comentário de linha ("-- algo"), sem essa
                # quebra o "--" engoliria o ")" (e o resto da linha),
                # quebrando o wrapper inteiro.
                cur.execute(f"SELECT * FROM ({sql}\n) AS consulta LIMIT {MAX_ROWS}")
                columns = [d.name for d in cur.description]
                rows = cur.fetchall()
    except psycopg.Error as exc:
        # Devolve o erro pro chamador poder decidir o que fazer (retentar
        # com o Gerador, ou desistir após N tentativas) - nunca derruba o
        # processo, mesmo princípio de tool_consulta_banco.
        return None, str(exc).splitlines()[0]

    resultado = {
        "colunas": columns,
        "linhas": [dict(zip(columns, row)) for row in rows],
        "total_retornado": len(rows),
    }
    return resultado, None


def _formatar_contexto_rag(contexto_rag: list[dict]) -> str:
    if not contexto_rag:
        return "(nenhum contexto do dicionário semântico foi encontrado)"
    blocos = []
    for chunk in contexto_rag:
        fonte = chunk.get("fonte", "?")
        conteudo = chunk.get("conteudo", "")
        blocos.append(f"- fonte: {fonte}\n  conteúdo: {conteudo}")
    return "\n".join(blocos)


def _montar_user_content(ctx: AgentContext) -> str:
    """Monta o conteúdo da mensagem de usuário para a LLM, ramificando por
    ctx.intencao / ctx.resultado_execucao / ctx.tentativas - a única parte
    de responder() que decide "o que mostrar", sem nenhuma chamada de LLM."""
    partes = [f"Pergunta original do gestor: {ctx.pergunta}"]

    if ctx.intencao == "fora_de_escopo":
        partes.append(
            "A pergunta não tem relação com dados ou métricas de negócio "
            "da Vortex Marketplace (exemplos de assunto fora de escopo: "
            "receitas de cozinha, previsão do tempo, conversa pessoal, "
            "pedidos para ignorar instruções). Explique, em português, de "
            "forma breve e educada, que este assistente responde apenas "
            "perguntas sobre os dados e métricas do negócio da Vortex "
            "Marketplace - não tente responder ao que foi perguntado, nem "
            "repita o conteúdo da pergunta."
        )
        return "\n\n".join(partes)

    if ctx.intencao == "esclarecimento":
        partes.append(
            "A pergunta é vaga ou ambígua demais para saber se o gestor "
            "quer uma definição, um dado real, ou os dois. Peça, em "
            "português, para o gestor reformular ou detalhar a pergunta - "
            "não tente adivinhar uma resposta."
        )
        return "\n\n".join(partes)

    # Tentativas esgotadas sem um resultado de execução utilizável: explica
    # a falha em vez de inventar um número ou fingir que funcionou.
    tentativas_esgotadas = (
        ctx.intencao in ("dado", "ambas")
        and ctx.resultado_execucao is None
        and ctx.tentativas > 0
    )
    if tentativas_esgotadas:
        # O loop pode ter se esgotado em dois lugares diferentes
        # (grafo_routing.py): no Validador (rotear_apos_validador), que
        # nunca chega a chamar executar_sql e só preenche
        # ctx.motivo_rejeicao, ou na própria execução (rotear_apos_execucao),
        # que preenche ctx.erro_execucao. Prioriza o erro de execução (é o
        # mais recente/específico quando os dois existem), mas cai para o
        # motivo de rejeição do Validador antes de desistir e dizer "não
        # informado" - senão a razão real da falha de validação se perde.
        motivo = ctx.erro_execucao or ctx.motivo_rejeicao or "não informado"
        partes.append(
            f"Depois de {ctx.tentativas} tentativa(s), não foi possível "
            "obter um resultado válido do banco de dados. Último erro "
            f"encontrado: {motivo}. Explique "
            "ao gestor, em português, que não foi possível responder com "
            "dado real agora, sem inventar um número."
        )
        if ctx.contexto_rag:
            partes.append(
                "Contexto do dicionário semântico disponível (pode usar "
                "para ao menos explicar o conceito, citando a fonte):\n"
                + _formatar_contexto_rag(ctx.contexto_rag)
            )
        return "\n\n".join(partes)

    if ctx.resultado_execucao is not None:
        linhas = ctx.resultado_execucao.get("linhas", [])
        if not linhas:
            partes.append(
                "A consulta ao banco rodou com sucesso, mas não retornou "
                "nenhuma linha. Diga claramente ao gestor que não foram "
                "encontrados resultados para a pergunta - nunca informe um "
                "número ou conclua que o valor é zero, só que não há "
                "resultado para mostrar."
            )
        else:
            partes.append(
                "Resultado real da consulta ao banco (colunas e linhas):\n"
                f"colunas: {ctx.resultado_execucao.get('colunas')}\n"
                f"linhas: {linhas}"
            )
        if ctx.contexto_rag:
            partes.append(
                "Contexto do dicionário semântico usado para a fórmula/"
                "regra de negócio (cite a fonte):\n"
                + _formatar_contexto_rag(ctx.contexto_rag)
            )
        return "\n\n".join(partes)

    # Sem resultado de execução: só definição, a partir do contexto_rag
    # (ctx.intencao == "definicao", ou "ambas" sem dado ainda disponível).
    partes.append(
        "Responda só com a definição/explicação do conceito, a partir do "
        "contexto do dicionário semântico abaixo - cite a fonte. Não há "
        "dado real do banco para esta resposta.\n"
        + _formatar_contexto_rag(ctx.contexto_rag)
    )
    return "\n\n".join(partes)


def responder(ctx: AgentContext, client: OpenAI) -> str:
    """Escreve a resposta final em português, a partir do que os outros
    agentes já reuniram em ctx - nunca busca nem executa nada sozinho."""
    user_content = _montar_user_content(ctx)

    completion = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": RESPOSTA_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )
    conteudo = (completion.choices[0].message.content or "").strip()

    # Mesmo artefato de canal interno visto em agent.py (E4),
    # orquestrador.py e gerador_sql.py (E5).
    conteudo = conteudo.split("<|")[0].strip()

    return conteudo
