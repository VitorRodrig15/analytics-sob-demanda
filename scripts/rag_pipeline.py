"""Entregável 3.3 (E3) - Pipeline RAG end-to-end.

Este é o script que junta as peças que já tinha prontas e as faz
funcionarem como um fluxo só, de ponta a ponta:

    pergunta -> retrieve() [3.1] -> build_messages() [3.4] -> LLM [3.2] -> resposta

É importante eu deixar registrado o escopo exato desta etapa: aqui o agente
responde com base no DICIONÁRIO (explica métricas, regras e exemplos, com
citação de fonte) - ele ainda não gera nem executa SQL de verdade contra o
banco dw. Isso é trabalho do Agente Gerador de SQL e do Agente de Execução,
que entram na E4 e na E5.

LATÊNCIA: cada chamada à LLM leva ~130-180s neste endpoint (a investigação
completa está em test_llm.py). Por isso o CLI avisa antes de chamar, pra
não parecer travado enquanto espera. Rode uma pergunta de cada vez; não
use isto num loop apertado - foi exatamente pensando nisso que separei a
bateria de testes (3.5) num script à parte, que roda em segundo plano.

Uso como módulo (de outro script, por exemplo o 3.5):
    from rag_pipeline import ask
    resultado = ask("qual o ticket medio?")

Uso como CLI (dentro do container):
    docker compose exec app python scripts/rag_pipeline.py "qual o ticket medio?"
    docker compose exec app python scripts/rag_pipeline.py "pergunta" --k 5 --salvar docs/respostas.jsonl
"""
import argparse
import json
import os
import time
import warnings
from dataclasses import asdict, dataclass
from pathlib import Path

from openai import OpenAI

from prompts import build_messages
from search import retrieve

warnings.filterwarnings("ignore")

LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-20b")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
MAX_TOKENS = 1200         # folga generosa: reasoning + resposta (ver nota em test_llm.py).
                          # Comecei com 800, mas na bateria do 3.5 uma resposta sobre
                          # churn de vendedores foi cortada no meio do SQL - subi para
                          # 1200 no mesmo dia e refiz o teste pra confirmar que resolveu.
TEMPERATURE = 0.2         # baixa de proposito: queremos respostas consistentes, nao criativas


@dataclass
class PipelineResult:
    pergunta: str
    chunks: list[dict]        # id, doc_type, title, similarity de cada chunk usado
    resposta: str
    tempo_segundos: float
    reasoning_chars: int      # tamanho do raciocinio interno (nao mostrado ao usuario)


def generate_answer(pergunta: str, chunks) -> tuple[str, float, int]:
    """Essa funcao e onde a espera de 130-180s acontece de verdade: chama a
    LLM com o contexto ja recuperado e mede quanto tempo levou. Retorna
    (resposta, tempo, reasoning_chars)."""
    client = OpenAI(base_url=NVIDIA_BASE_URL, api_key=os.environ["NVIDIA_API_KEY"])
    messages = build_messages(pergunta, chunks)

    start = time.perf_counter()
    completion = client.chat.completions.create(
        model=LLM_MODEL, messages=messages, temperature=TEMPERATURE, max_tokens=MAX_TOKENS,
    )
    elapsed = time.perf_counter() - start

    message = completion.choices[0].message
    reasoning = getattr(message, "reasoning_content", None) or ""
    resposta = (message.content or "").strip()
    if not resposta:
        # mesmo com max_tokens generoso isso pode acontecer; melhor avisar do que devolver vazio
        resposta = "(a LLM nao retornou texto - gastou o limite de tokens so no raciocinio interno)"

    return resposta, round(elapsed, 1), len(reasoning)


def ask(pergunta: str, k: int = 3) -> PipelineResult:
    """A funcao que resume o entregavel 3.3 inteiro: roda o pipeline completo
    (busca o contexto e gera a resposta) e devolve o resultado estruturado.
    De proposito sem nenhum print - pensada pra ser chamada de outro script,
    como fiz na bateria de 12 perguntas do 3.5."""
    chunks = retrieve(pergunta, k=k)
    resposta, tempo, reasoning_chars = generate_answer(pergunta, chunks)
    return PipelineResult(
        pergunta=pergunta,
        chunks=[{"id": c.id, "doc_type": c.doc_type, "title": c.title,
                 "similarity": round(c.similarity, 3)} for c in chunks],
        resposta=resposta,
        tempo_segundos=tempo,
        reasoning_chars=reasoning_chars,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pergunta")
    parser.add_argument("--k", type=int, default=3, help="quantidade de chunks (padrao 3)")
    parser.add_argument("--salvar", help="caminho de um .jsonl para acrescentar o resultado")
    args = parser.parse_args()

    print(f'Pergunta: "{args.pergunta}"\n')

    print("1/3  buscando os chunks mais relevantes no banco vetorial...")
    chunks = retrieve(args.pergunta, k=args.k)
    print(f"     {len(chunks)} chunks encontrados:")
    for c in chunks:
        print(f"       - [{c.doc_type}] {c.title} (similaridade {c.similarity:.2f})")

    print("\n2/3  chamando o GPT-OSS-20B com o contexto recuperado...")
    print("     (leva entre 130 e 180 segundos neste endpoint - aguarde)")
    resposta, tempo, reasoning_chars = generate_answer(args.pergunta, chunks)
    print(f"     resposta recebida em {tempo}s ({reasoning_chars} caracteres de raciocinio interno)")

    print("\n3/3  resposta final:\n")
    print(resposta)

    if args.salvar:
        resultado = PipelineResult(
            pergunta=args.pergunta,
            chunks=[{"id": c.id, "doc_type": c.doc_type, "title": c.title,
                     "similarity": round(c.similarity, 3)} for c in chunks],
            resposta=resposta, tempo_segundos=tempo, reasoning_chars=reasoning_chars,
        )
        path = Path(args.salvar)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(resultado), ensure_ascii=False) + "\n")
        print(f"\nResultado acrescentado em {path}")


if __name__ == "__main__":
    main()
