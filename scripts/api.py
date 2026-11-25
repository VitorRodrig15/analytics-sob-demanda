"""Entregavel 6 (E6) - API REST (itens 6.1 e 6.2) que expõe o sistema
multiagente.

6.1: casca da API - endpoints, validação via Pydantic, documentação
automática (Swagger em /docs).
6.2: /perguntar chama o grafo de verdade (run_grafo, de grafo.py) e
devolve o AgentContext final convertido pra JSON - resposta, fontes
citadas (contexto_rag) e o historico passo a passo dos agentes.

Uso (dentro do container):
    docker compose exec app uvicorn api:app --host 0.0.0.0 --port 8000 --app-dir scripts

Depois, com o container rodando, acessar http://localhost:8000/docs
"""
import logging

from pydantic import BaseModel

from fastapi import FastAPI, HTTPException

from grafo import run_grafo

logger = logging.getLogger("api")

app = FastAPI(
    title="Vortex Analytics Copilot - API",
    description=(
        "API REST do sistema multiagente da Vortex Marketplace para analise "
        "de dados sob demanda (Entregavel 6)."
    ),
    version="0.1.0",
)


class PerguntaRequest(BaseModel):
    pergunta: str


class Fonte(BaseModel):
    fonte: str
    tipo: str
    similaridade: float


class PerguntaResponse(BaseModel):
    resposta: str
    fontes: list[Fonte]
    tentativas: int
    historico: list[str]


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/perguntar", response_model=PerguntaResponse)
def perguntar(request: PerguntaRequest) -> PerguntaResponse:
    # run_grafo e sincrono e bloqueante: a requisicao HTTP fica esperando o
    # grafo inteiro terminar (pode levar alguns segundos, mais se o loop de
    # correcao disparar) antes de devolver a resposta.
    #
    # Captura ampla de proposito: o grafo chama a LLM (openai.APIError e
    # subclasses) e o modelo de embeddings via requests (langchain-nvidia-
    # ai-endpoints), e ambos ja tiveram falha transitoria real documentada
    # no addendum da E5 (instabilidade/cold-start da API da NVIDIA). Sem
    # isso, qualquer uma dessas falhas sobe crua como 500 sem explicacao -
    # aqui vira um 503 com motivo, e o traceback real fica logado pra quem
    # for depurar depois.
    try:
        ctx = run_grafo(request.pergunta)
    except Exception:
        logger.exception("Falha ao rodar o grafo para a pergunta: %r", request.pergunta)
        raise HTTPException(
            status_code=503,
            detail=(
                "Nao foi possivel completar a consulta no momento - "
                "provavel instabilidade pontual da API da NVIDIA (LLM ou "
                "embeddings). Tente novamente em alguns instantes."
            ),
        )

    return PerguntaResponse(
        resposta=ctx.resposta_final,
        fontes=[Fonte(**f) for f in ctx.contexto_rag],
        tentativas=ctx.tentativas,
        historico=ctx.historico,
    )
