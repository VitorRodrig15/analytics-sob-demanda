"""Entregável 3.2 (E3) - Teste de conexão com a LLM (GPT-OSS-20B via NVIDIA NIM).

Este script confirma uma coisa simples: que a chave da NVIDIA também
funciona para conversar com a LLM, não só para gerar embeddings (que já
usávamos desde a E2). É o "chamadas de teste bem-sucedidas" que o
entregável pede.

Só que foi aqui que apareceu o maior perrengue da semana, e não era sobre
o código. O GPT-OSS-20B leva ~130-180 SEGUNDOS por chamada, mesmo numa
pergunta de uma frase. Antes de aceitar isso como normal, investiguei a
fundo (dia 03/11) pra descartar as causas mais óbvias:
  - conexao com a API: rapida (GET /v1/models ~0.5s) -> nao e rede
  - 2a chamada logo apos a 1a: continuou lenta (182s -> 128s) -> nao e "modelo frio"
  - streaming: ~148s ate o 1o token, depois o resto sai em <1s -> a demora e
    antes de comecar a gerar, nao durante a escrita
  - extra_body={"reasoning_effort": "low"|"medium"|"high"}: tempo igual nos
    3 niveis (143s/136s/144s) -> nao e o tamanho do raciocinio interno

Conclusão: é fila/limite do lado da NVIDIA (tier gratuito), fora do meu
controle. Isso muda como vou demonstrar o projeto daqui pra frente:
  - o pipeline (3.3) faz pelo menos 2 chamadas a LLM por pergunta (SQL +
    narrativa) -> ~5 min por pergunta, acima da meta de <2min que defini na E1
  - para qualquer demo ao vivo, mais seguro mostrar respostas pre-computadas
  - sempre usar max_tokens generoso (500+): com valores baixos o modelo pode
    gastar tudo "pensando" (reasoning) e devolver a resposta vazia

Uso (dentro do container):  docker compose exec app python scripts/test_llm.py
"""
import os
import time

from openai import OpenAI

LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-20b")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
LATENCIA_ESPERADA_SEGUNDOS = (130, 180)  # ver investigacao no docstring acima

PERGUNTAS_TESTE = [
    "Responda em uma frase: o que é um marketplace de e-commerce?",
    "Qual é a capital do Brasil?",
]


def main() -> None:
    client = OpenAI(base_url=NVIDIA_BASE_URL, api_key=os.environ["NVIDIA_API_KEY"])

    print(f"Modelo: {LLM_MODEL}")
    print(f"Endpoint: {NVIDIA_BASE_URL}\n")

    for pergunta in PERGUNTAS_TESTE:
        start = time.perf_counter()
        completion = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": pergunta}],
            temperature=0.2,
            max_tokens=500,  # folga para o reasoning + a resposta (ver nota de latencia acima)
        )
        elapsed = time.perf_counter() - start

        message = completion.choices[0].message
        reasoning = getattr(message, "reasoning_content", None)

        print(f"Pergunta: {pergunta}")
        if reasoning:
            print(f"  [raciocinio interno, {len(reasoning)} caracteres - nao mostrado ao usuario]")
        print(f"  Resposta: {message.content.strip()}")
        print(f"  Tempo: {elapsed:.1f}s | tokens: {completion.usage.total_tokens}\n")

    print("Conexao com a LLM confirmada.")


if __name__ == "__main__":
    main()
