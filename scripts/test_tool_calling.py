"""Entregável 4.1 (E4) - Teste: o GPT-OSS-20B aceita tool calling? (passo 1 do plano)

Antes de desenhar o agente de verdade, preciso confirmar que o modelo
consegue usar o parametro "tools" da API (formato OpenAI) e devolver uma
chamada de funcao estruturada, em vez de so texto. Se isso nao funcionar
aqui, todo o resto da E4 muda de abordagem.

Uso duas ferramentas ficticias de proposito (nao sao as reais do projeto):
  - "consultar_estoque"   : para uma pergunta que exige usa-la
  - "consultar_previsao_tempo" : uma ferramenta "isca", que nao deveria ser
    chamada na pergunta de teste - serve para ver se o modelo so chama
    quando faz sentido, ou se chama ferramentas aleatoriamente.

LATENCIA: cada chamada leva ~130-180s (ver test_llm.py). Com tool calling
pode levar 2 chamadas (decisao + resposta final apos o resultado da tool),
entao este teste pode levar uns 5 minutos.

Uso (dentro do container):  docker compose exec app python scripts/test_tool_calling.py
"""
import json
import os

from openai import OpenAI

LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-20b")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "consultar_estoque",
            "description": "Consulta a quantidade em estoque de um produto pelo nome.",
            "parameters": {
                "type": "object",
                "properties": {
                    "produto": {"type": "string", "description": "Nome do produto"},
                },
                "required": ["produto"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_previsao_tempo",
            "description": "Consulta a previsão do tempo de uma cidade.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cidade": {"type": "string", "description": "Nome da cidade"},
                },
                "required": ["cidade"],
            },
        },
    },
]


def fake_tool_result(name: str, args: dict) -> str:
    """Simula a execução da ferramenta - aqui so pra testar o protocolo, não
    o conteúdo real (isso vem no passo 3, com as ferramentas de verdade)."""
    if name == "consultar_estoque":
        return json.dumps({"produto": args.get("produto"), "quantidade": 42})
    return json.dumps({"erro": "ferramenta não deveria ter sido chamada nesta pergunta"})


def main() -> None:
    client = OpenAI(base_url=NVIDIA_BASE_URL, api_key=os.environ["NVIDIA_API_KEY"])

    messages = [
        {"role": "system", "content": "Você é um assistente de operações de loja."},
        {"role": "user", "content": "Quantas unidades do produto 'fone de ouvido' temos em estoque?"},
    ]

    print("1/2  enviando a pergunta com 2 ferramentas disponíveis (aguarde ~150s)...")
    completion = client.chat.completions.create(
        model=LLM_MODEL, messages=messages, tools=TOOLS, tool_choice="auto",
        temperature=0.2, max_tokens=800,
    )
    message = completion.choices[0].message
    tool_calls = getattr(message, "tool_calls", None)

    print(f"\nfinish_reason: {completion.choices[0].finish_reason}")
    if not tool_calls:
        print("RESULTADO: o modelo NÃO pediu nenhuma tool call.")
        print(f"Respondeu direto em texto: {message.content!r}")
        return

    print(f"RESULTADO: o modelo pediu {len(tool_calls)} chamada(s) de ferramenta:")
    for call in tool_calls:
        print(f"  - {call.function.name}({call.function.arguments})")

    # Verifica se chamou a ferramenta certa (estoque) e não a isca (tempo)
    names_called = {c.function.name for c in tool_calls}
    if names_called == {"consultar_estoque"}:
        print("  -> Decisão correta: só chamou a ferramenta relevante.")
    else:
        print(f"  -> Atenção: esperava só 'consultar_estoque', veio {names_called}")

    # Executa as tools (simuladas) e manda o resultado de volta, pra ver se o
    # modelo usa a informação pra responder (fecha o ciclo do tool calling)
    messages.append(message)
    for call in tool_calls:
        args = json.loads(call.function.arguments)
        result = fake_tool_result(call.function.name, args)
        messages.append({"role": "tool", "tool_call_id": call.id, "content": result})

    print("\n2/2  mandando o resultado da ferramenta de volta pro modelo (aguarde ~150s)...")
    completion2 = client.chat.completions.create(
        model=LLM_MODEL, messages=messages, tools=TOOLS, temperature=0.2, max_tokens=800,
    )
    final = completion2.choices[0].message.content
    print(f"\nResposta final, após receber o resultado da ferramenta:\n{final}")


if __name__ == "__main__":
    main()
