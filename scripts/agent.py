"""Entregáveis 4.1 e 4.2 (E4) - Primeiro agente funcional, com tool calling de verdade.

Esta é a virada conceitual da E3 para a E4. No rag_pipeline.py (3.3), EU
decidia o caminho em Python: sempre busca -> sempre monta prompt -> sempre
chama a LLM, igual pra toda pergunta. Aqui é o contrário: a LLM recebe a
lista de ferramentas (tools.py, 4.3) e decide sozinha, a cada pergunta,
se busca no dicionário, se consulta o banco, as duas coisas, ou nenhuma.

Papel do agente (o que o 4.5 vai documentar com mais detalhe):
  - Recebe a pergunta de um gestor de negócio.
  - Decide, chamando busca_vetorial, qual é a definição/fórmula/regra certa
    antes de supor qualquer coisa de memória.
  - Se a pergunta pedir um número real (não só uma definição), decide
    chamar consulta_banco com o SQL que ele mesmo escreve, seguindo a
    fórmula que acabou de buscar.
  - Produz uma resposta final em texto, citando a fonte da definição usada.

Isso ainda é UM agente isolado, não os 5 da arquitetura da E1 - é o
protótipo que mistura um pouco do papel do Agente Semântico/RAG e do
Agente de Execução. A separação em 5 agentes especializados, orquestrados,
é o trabalho da E5.

LATÊNCIA: cada "rodada" (decisão da LLM) leva ~130-180s, e uma pergunta
pode precisar de 2 a 4 rodadas (buscar -> consultar -> responder). Por
isso o CLI mostra o progresso rodada a rodada - sem isso pareceria travado
por muitos minutos.

Uso como módulo:
    from agent import run_agent
    resultado = run_agent("qual foi a receita de 2017?")

Uso como CLI (dentro do container):
    docker compose exec app python scripts/agent.py "qual foi a receita de 2017?"
"""
import argparse
import json
import os
from dataclasses import asdict, dataclass, field

from openai import OpenAI

from tools import TOOLS, execute_tool

LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-20b")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
MAX_TOKENS = 1200
TEMPERATURE = 0.2
MAX_RODADAS = 5  # trava de seguranca contra loop infinito de tool calls

AGENT_SYSTEM_PROMPT = """\
Você é o assistente de analytics da Vortex Marketplace, um marketplace \
B2C brasileiro. Você ajuda gestores de negócio que não sabem SQL a \
entender métricas e consultar dados reais da empresa.

Fato fixo, válido sempre: a data de referência ("hoje") para qualquer \
cálculo de período é 2018-08-31. "Este ano" = 2018. "Último trimestre" = \
01/06/2018 a 31/08/2018. Os dados confiáveis só existem até essa data.

Você tem duas ferramentas disponíveis:
- busca_vetorial: consulta o dicionário semântico (definições, fórmulas, \
regras de negócio, descrição de tabelas, exemplos de SQL validados).
- consulta_banco: executa um SELECT de verdade no schema dw.

Regras que você deve seguir sempre:
1. Antes de escrever qualquer SQL, chame busca_vetorial para confirmar a \
fórmula e os filtros obrigatórios da métrica - nunca escreva uma fórmula \
de memória, mesmo que pareça óbvia.
2. Só chame consulta_banco quando o gestor pedir um número, uma \
comparação ou uma lista real - se a pergunta for só sobre o que uma \
métrica significa, busca_vetorial sozinho já basta.
3. Se busca_vetorial indicar que uma métrica é indisponível (ex.: margem \
de contribuição), explique o motivo e sugira uma alternativa - não tente \
consultar o banco mesmo assim.
4. Se consulta_banco devolver um erro, leia o erro e tente corrigir a \
consulta uma vez; se persistir, explique ao gestor o que não foi possível \
responder, não invente um número.
5. Sempre cite a fonte da definição usada, no formato "(fonte: <título>)".
6. Nunca peça nem tente executar um comando de escrita (INSERT, UPDATE, \
DELETE, DROP...) - essas operações não existem para você, nem como teste.
7. Responda em português do Brasil, direto, sem expor o SQL cru a menos \
que o gestor peça explicitamente. Valores em R$ com 2 casas, percentuais \
com "%".
8. Região, cidade e estado do CLIENTE estão em dw.customers \
(customer_region, customer_city, customer_state), e do VENDEDOR em \
dw.sellers (seller_region, seller_city, seller_state) - a tabela \
dw.orders não tem essas colunas. Se uma busca no dicionário não achar a \
informação de primeira, tente de novo com um termo mais específico (ex.: \
"customer_region" em vez de só "cidade") antes de desistir.\
"""


@dataclass
class ToolCallLog:
    nome: str
    argumentos: dict
    resultado: str


@dataclass
class AgentResult:
    pergunta: str
    chamadas: list[ToolCallLog] = field(default_factory=list)
    resposta: str = ""
    rodadas: int = 0


def run_agent(pergunta: str, verbose: bool = False) -> AgentResult:
    """Roda o loop do agente: a LLM decide, a cada rodada, se chama uma
    ferramenta ou se já tem o suficiente para responder. Sem prints por
    padrão - pensado pra ser chamado de outro script, como os testes do 4.4."""
    client = OpenAI(base_url=NVIDIA_BASE_URL, api_key=os.environ["NVIDIA_API_KEY"])
    messages = [
        {"role": "system", "content": AGENT_SYSTEM_PROMPT},
        {"role": "user", "content": pergunta},
    ]
    result = AgentResult(pergunta=pergunta)

    for rodada in range(1, MAX_RODADAS + 1):
        result.rodadas = rodada
        if verbose:
            print(f"  rodada {rodada}/{MAX_RODADAS}: chamando a LLM (~130-180s)...")

        completion = client.chat.completions.create(
            model=LLM_MODEL, messages=messages, tools=TOOLS, tool_choice="auto",
            temperature=TEMPERATURE, max_tokens=MAX_TOKENS,
        )
        message = completion.choices[0].message
        tool_calls = getattr(message, "tool_calls", None)

        if not tool_calls:
            result.resposta = (message.content or "").strip()
            if not result.resposta:
                result.resposta = "(a LLM não retornou texto nesta rodada)"
            return result

        messages.append(message)
        for call in tool_calls:
            # O GPT-OSS as vezes devolve o nome da funcao com um artefato do
            # seu formato interno de "canais" colado no final, tipo
            # "consulta_banco<|channel|>commentary" em vez de so
            # "consulta_banco". Sem isso, cai sempre em "ferramenta
            # desconhecida" e o agente repete a mesma tentativa ate o limite
            # de rodadas - foi exatamente o que vi no primeiro teste.
            nome = call.function.name.split("<|")[0]
            args = json.loads(call.function.arguments or "{}")
            if verbose:
                print(f"    -> {nome}({args})")
            tool_result = execute_tool(nome, args)
            result.chamadas.append(ToolCallLog(nome, args, tool_result))
            messages.append({"role": "tool", "tool_call_id": call.id, "content": tool_result})

    result.resposta = "(o agente não concluiu em até 5 rodadas - possível loop de tool calls)"
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pergunta")
    args = parser.parse_args()

    print(f'Pergunta: "{args.pergunta}"\n')
    result = run_agent(args.pergunta, verbose=True)

    print(f"\n{len(result.chamadas)} chamada(s) de ferramenta em {result.rodadas} rodada(s):")
    for call in result.chamadas:
        print(f"  - {call.nome}({call.argumentos})")

    print(f"\nResposta final:\n{result.resposta}")


if __name__ == "__main__":
    main()
