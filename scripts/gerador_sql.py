"""Entregável 5 (E5) - Agente Gerador de SQL.

Terceiro agente da arquitetura: depois que o Agente Semântico/RAG (Task 4)
busca a definição/fórmula certa no dicionário e o Orquestrador (Task 5)
decide que a pergunta pede dado real, alguém precisa escrever o SELECT.
Esse "alguém" é este agente - ele só escreve SQL, nunca executa (isso é
papel do Agente de Execução) e nunca valida (isso é papel do Validador,
outra task). Recebe o contexto_rag já buscado (não busca nada sozinho) e,
se a tentativa anterior falhou na execução ou na validação, recebe o
motivo para corrigir na nova tentativa.

Uso como módulo:
    from openai import OpenAI
    from gerador_sql import gerar_sql
    sql = gerar_sql("qual foi a receita de 2017?", contexto_rag, None, client)
"""
import os

from openai import OpenAI

LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-20b")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
# 1500, não 700: a bateria de testes de integração real (Task 5.5,
# docs/e5_testes_integracao.jsonl) mostrou que 700 ainda truncava a
# resposta antes do SELECT saír inteiro em perguntas mais complexas -
# todas as 8 rejeições do Validador registradas na bateria eram, na
# verdade, saída vazia/truncada do gerador ("Esperado exatamente 1
# instrucao SQL, encontrado 0" ou erro de parse por SQL cortado no meio),
# nenhuma era uma violação real de schema/tipo de statement. Mesmo
# artefato de canal de raciocínio interno visto no agent.py da E4 e no
# orquestrador.py da E5 - lição carregada de lá -, só que aqui a resposta
# final é uma consulta SQL inteira (às vezes com múltiplas CTEs), não uma
# palavra só, então precisa de bem mais folga do que os 150 do
# orquestrador.
MAX_TOKENS = 1500
TEMPERATURE = 0.2

GERADOR_SQL_SYSTEM_PROMPT = """\
Você escreve consultas SQL para o Agente Gerador de SQL da Vortex \
Marketplace, um marketplace B2C brasileiro. Você recebe a pergunta de um \
gestor de negócio e trechos do dicionário semântico (fórmulas, regras de \
negócio, descrição de tabelas, exemplos de SQL validados) já buscados por \
outro agente, e devolve só a consulta SQL que responde à pergunta.

Fato fixo, válido sempre: a data de referência ("hoje") para qualquer \
cálculo de período é 2018-08-31. "Este ano" = 2018. "Último trimestre" = \
01/06/2018 a 31/08/2018. Os dados confiáveis só existem até essa data.

Regra de localização (erro comum, preste atenção): região, cidade e estado \
do CLIENTE estão em dw.customers (customer_region, customer_city, \
customer_state), e do VENDEDOR em dw.sellers (seller_region, seller_city, \
seller_state) - a tabela dw.orders NÃO tem essas colunas.

Regras que você deve seguir sempre:
1. Use só o schema dw, baseando a fórmula e os filtros obrigatórios no \
contexto do dicionário semântico recebido - nunca escreva uma fórmula de \
memória, mesmo que pareça óbvia, se ela não estiver no contexto. Pelo \
mesmo motivo, nunca invente nome de tabela ou de coluna que não esteja no \
contexto do dicionário semântico recebido ou na regra de localização \
abaixo - toda consulta tem que referenciar ao menos uma tabela real de dw.*.
2. Escreva só um comando de leitura, começando por SELECT ou WITH. Nunca \
escreva INSERT, UPDATE, DELETE, DROP ou qualquer outro comando de escrita.
3. Devolva só o SQL puro, sem markdown, sem crases (```), sem comentários, \
sem explicação em texto - nada além da consulta.\
"""


def _formatar_contexto(contexto_rag: list[dict]) -> str:
    if not contexto_rag:
        return "(nenhum contexto do dicionário semântico foi encontrado)"
    blocos = []
    for chunk in contexto_rag:
        fonte = chunk.get("fonte", "?")
        conteudo = chunk.get("conteudo", "")
        blocos.append(f"- fonte: {fonte}\n  conteúdo: {conteudo}")
    return "\n".join(blocos)


def gerar_sql(
    pergunta: str,
    contexto_rag: list[dict],
    erro_anterior: str | None,
    client: OpenAI,
) -> str:
    """Gera a consulta SQL para a pergunta, usando o contexto do dicionário
    semântico já buscado por outro agente. Não executa nem valida o SQL -
    só escreve a string, limpa de cercas de markdown se vierem."""
    user_content = (
        f"Pergunta do gestor: {pergunta}\n\n"
        f"Contexto do dicionário semântico:\n{_formatar_contexto(contexto_rag)}"
    )
    if erro_anterior is not None:
        user_content += f"\n\nA tentativa anterior falhou por: {erro_anterior}. Corrija."

    completion = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": GERADOR_SQL_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )
    escolha = completion.choices[0]
    conteudo = (escolha.message.content or "").strip()

    # finish_reason == "length" é um modo de falha diferente de uma
    # resposta vazia/truncada por outro motivo: o MAX_TOKENS acabou antes
    # do modelo terminar o SELECT. Isso não deve "parecer" uma resposta
    # saudável igual a uma string vazia comum (achado da revisão final:
    # era exatamente essa truncagem, não uma violação real de schema, que
    # causava toda rejeição do Validador na bateria de integração) - loga
    # no próprio conteúdo retornado pra quem for investigar o
    # erro_anterior/motivo_rejeicao no historico não confundir isso com
    # "a LLM simplesmente não respondeu nada".
    if escolha.finish_reason == "length" and not conteudo:
        conteudo = (
            "-- ERRO: resposta truncada por limite de tokens (finish_reason=length), "
            "sem SQL completo gerado"
        )

    # Mesmo artefato de canal interno visto no agent.py (E4) e no
    # orquestrador.py (E5): a LLM as vezes cola algo como
    # "SELECT ...<|channel|>commentary" no final.
    conteudo = conteudo.split("<|")[0].strip()

    # Remove cercas de código markdown (```sql ou ```), se vierem.
    if conteudo.startswith("```"):
        linhas = conteudo.split("\n")
        linhas = linhas[1:]  # remove a linha de abertura (``` ou ```sql)
        if linhas and linhas[-1].strip() == "```":
            linhas = linhas[:-1]
        elif linhas and linhas[-1].strip().endswith("```"):
            linhas[-1] = linhas[-1].rstrip("`").rstrip()
        conteudo = "\n".join(linhas).strip()

    return conteudo
