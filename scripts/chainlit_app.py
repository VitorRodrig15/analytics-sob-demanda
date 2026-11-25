"""Entregavel 6 (E6) - Frontend (itens 6.3, 6.4 e 6.5), feito com Chainlit.

Importante: este frontend NAO chama o grafo diretamente (nao importa
grafo.py nem roda LLM aqui). Ele consome a API FastAPI (scripts/api.py) via
HTTP, como pede o item 6.4 - a mesma API que qualquer outro cliente
(curl, Postman, outro sistema) poderia chamar. Isso mantem frontend e
backend desacoplados: o frontend pode trocar (ou ser hospedado em outro
lugar, como um GitHub Pages estatico, se um dia reescrito em HTML/JS puro)
sem precisar tocar na API.

Uso (dentro do container, com a API ja rodando na porta 8000):
    docker compose exec app chainlit run chainlit_app.py --host 0.0.0.0 --port 8001 -w --app-dir scripts

Depois, acessar http://localhost:8001
"""
import os

import httpx

import chainlit as cl

API_URL = os.getenv("API_URL", "http://localhost:8000")

# Tempo generoso: o /perguntar da API e sincrono e pode esperar o grafo
# rodar ate MAX_TENTATIVAS=3 voltas do loop de correcao (ver scripts/api.py
# e scripts/grafo.py) - visto na pratica levar ate ~1 min nos piores casos.
TIMEOUT_SEGUNDOS = 120.0


@cl.on_message
async def ao_receber_mensagem(mensagem: cl.Message) -> None:
    # cl.Message(content="").send() cria a bolha de resposta vazia na tela
    # ANTES da chamada HTTP comecar - e o indicador de "processando" (6.5):
    # o Chainlit ja mostra um indicador de atividade proprio enquanto o
    # handler roda, mas atualizar o texto da mensagem com o status da
    # chamada deixa mais claro o que esta acontecendo (nao e so um spinner
    # generico).
    resposta_msg = cl.Message(content="")
    await resposta_msg.send()

    resposta_msg.content = "_Consultando o sistema multiagente..._"
    await resposta_msg.update()

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SEGUNDOS) as client:
            r = await client.post(
                f"{API_URL}/perguntar", json={"pergunta": mensagem.content}
            )
            r.raise_for_status()
            dados = r.json()
    except httpx.TimeoutException:
        resposta_msg.content = (
            "A API demorou demais para responder (timeout). "
            "Tente novamente - pode ter sido uma instabilidade pontual "
            "do modelo de embeddings (ver addendum da E5)."
        )
        await resposta_msg.update()
        return
    except httpx.HTTPStatusError as exc:
        # A API devolve {"detail": "..."} (FastAPI/HTTPException) com um
        # motivo legivel quando o grafo falha (ver scripts/api.py) - extrai
        # isso em vez de mostrar só o texto generico do erro HTTP.
        try:
            detalhe = exc.response.json().get("detail")
        except Exception:
            detalhe = None
        resposta_msg.content = detalhe or (
            f"A API respondeu com erro ({exc.response.status_code}) "
            "ao processar a pergunta."
        )
        await resposta_msg.update()
        return
    except httpx.HTTPError as exc:
        # Erro de conexao de verdade (API fora do ar, endereco errado) -
        # nao e um erro vindo do grafo, e sim de nao conseguir falar com a
        # API.
        resposta_msg.content = f"Não foi possível conectar à API ({API_URL}): {exc}"
        await resposta_msg.update()
        return

    # A resposta_final dos agentes ja vem formatada em Markdown (negrito,
    # listas) - o Chainlit renderiza Markdown nativamente, entao so precisa
    # passar o texto direto, sem reformatar nada (6.5: "formatacao
    # adequada").
    resposta_msg.content = dados["resposta"]

    # Fontes/referencias (6.5) - exibidas separadas da resposta principal,
    # como elementos de texto a parte, citando de onde veio o trecho de
    # contexto que a API devolveu (campo "fontes" de PerguntaResponse).
    if dados.get("fontes"):
        elementos = [
            cl.Text(
                name=f"Fonte {i + 1}: {f['fonte']}",
                content=f"Tipo: {f['tipo']}\nSimilaridade: {f['similaridade']}",
                display="inline",
            )
            for i, f in enumerate(dados["fontes"])
        ]
        resposta_msg.elements = elementos

    await resposta_msg.update()
