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
from pydantic import BaseModel

from fastapi import FastAPI

from grafo import run_grafo

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
    ctx = run_grafo(request.pergunta)

    return PerguntaResponse(
        resposta=ctx.resposta_final,
        fontes=[Fonte(**f) for f in ctx.contexto_rag],
        tentativas=ctx.tentativas,
        historico=ctx.historico,
    )
