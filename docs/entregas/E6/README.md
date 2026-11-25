# E6 — API e Interface do Usuário

**Período:** 24/11 a 28/11/2026 · **Foco:** Interface · **Status:** 🚧 Em andamento (6.1 a 6.5 funcionando, ver "O que ainda falta" abaixo)

Esta entrega cobre os itens 6.1 a 6.5: expor o grafo multiagente da E5 por trás de
uma API REST, e construir um frontend de verdade pra alguém sem acesso ao terminal
conseguir usar o sistema. Até aqui (E1 a E5), o único jeito de rodar o sistema era
`docker compose exec app python scripts/grafo.py "pergunta"` — ninguém de negócio
ia conseguir usar isso.

## 6.1 API REST com FastAPI

[`scripts/api.py`](../../../scripts/api.py) expõe dois endpoints: `GET /health`
(checagem simples) e `POST /perguntar` (recebe `{"pergunta": "..."}` e devolve a
resposta). Os modelos de entrada/saída são `Pydantic` (`PerguntaRequest`,
`PerguntaResponse`, `Fonte`), e é a partir deles que o FastAPI gera sozinho a
documentação Swagger/OpenAPI em `/docs` — não escrevi nenhuma linha de doc manual,
só tipei os modelos direito.

## 6.2 Integração API ↔ Multi-Agentes

O endpoint `/perguntar` chama `run_grafo()` direto de
[`scripts/grafo.py`](../../../scripts/grafo.py) — a mesma função que a E5 já usava
na CLI, sem duplicar nenhuma lógica. Testei com a mesma pergunta do 5.4 ("qual foi a
receita de 2017?") e bateu o mesmo valor já confirmado (**R$ 5.962.902,01**),
incluindo as fontes citadas e o `historico` passo a passo dos agentes.

A chamada é síncrona e bloqueante: a requisição HTTP fica esperando o grafo
inteiro terminar (pode levar alguns segundos, mais se o loop de correção
disparar) — é por isso que o indicador de carregamento do 6.5 importa.

## 6.3 e 6.4 Frontend (Chainlit) e integração com a API

Optei por [Chainlit](https://docs.chainlit.io) pro frontend (recomendação do
supervisor) em vez de montar HTML/JS do zero: ele já entrega chat pronto,
streaming, histórico e indicador de atividade, deixando o tempo da semana focado
no 6.1/6.2, que é a parte que prova a integração de verdade.

[`scripts/chainlit_app.py`](../../../scripts/chainlit_app.py) **não importa o
grafo nem chama LLM nenhuma diretamente** — ele consome a API via HTTP
(`httpx`), exatamente como pede o item 6.4. Isso mantém frontend e backend
desacoplados: a API pode ser chamada por qualquer outro cliente (curl, outro
sistema), e o frontend podia, em tese, ser hospedado em outro lugar sem tocar
na API.

**Um detalhe que só apareceu rodando de verdade:** o Chainlit detecta sozinho a
variável de ambiente `DATABASE_URL` (que já existia no projeto pro SQLAlchemy) e
tenta ligar um recurso próprio de persistência de histórico de chat no mesmo
Postgres — o que quebrava com `ModuleNotFoundError: No module named 'asyncpg'`
(dependência que não instalamos, de propósito: esse recurso não faz parte do
escopo desta entrega, e criaria tabelas do Chainlit dentro do mesmo banco sem
revisão). A solução foi rodar o processo do Chainlit sem essa variável
específica — o `chainlit_app.py` não acessa o banco diretamente mesmo, só fala
HTTP com a API.

## 6.5 Experiência do usuário

- **Indicador de carregamento:** a mensagem de resposta já nasce na tela com
  `"Consultando o sistema multiagente..."` antes da chamada HTTP terminar, em vez
  de deixar a tela parada sem explicação.
- **Fontes/referências:** cada trecho do contexto RAG que a API devolve
  (`fontes`, com `tipo` e `similaridade`) aparece como elemento separado na
  resposta, não misturado no texto corrido.
- **Formatação:** a `resposta_final` dos agentes já vem em Markdown (negrito,
  código inline) desde a E5 — o Chainlit renderiza nativamente, sem precisar
  reformatar nada do lado do frontend.
- **Tratamento de erro:** timeout da API e erro de conexão têm mensagens
  próprias no frontend, diferentes de uma resposta válida de "não consegui
  responder" vinda do próprio grafo (esse segundo caso é um HTTP 200 normal, não
  um erro). Achado testando manualmente: uma falha real dentro do grafo (ex.:
  instabilidade pontual da API da NVIDIA) subia crua como HTTP 500 sem
  explicação nenhuma pro usuário. Corrigido capturando a exceção em
  `scripts/api.py` (vira um 503 com motivo, e o traceback real fica logado
  server-side) e extraindo essa mensagem no `chainlit_app.py` em vez de
  mostrar o texto genérico do erro HTTP. Testei forçando o erro de propósito
  (chave de API inválida só nesse processo) antes e depois da correção.

Testei manualmente os 3 caminhos principais do grafo pelo chat: pergunta de
definição (pula SQL/Validador), pergunta ambígua (pede esclarecimento, sem
fontes) e consulta válida sem resultado (filtro logicamente impossível, mesmo
cenário do 7b da E5) — todos bateram com o comportamento documentado na E5.

**Achado testando uma pergunta propositalmente fora do domínio** ("pode me
passar a receita de um bolo de maracujá?"): o Orquestrador não tinha
categoria nenhuma pra "isso não é sobre o negócio" - a pergunta era forçada
numa das 4 categorias existentes, o que ora gerava uma resposta aceitável por
acaso, ora uma falha real e intermitente. Corrigido adicionando uma 5ª
categoria (`fora_de_escopo`) ao classificador - documentado como addendum em
[docs/entregas/E5/README.md](../E5/README.md#adendo-23112026-categoria-fora_de_escopo-adicionada-na-e6),
já que mexe numa parte da arquitetura que a E5 tinha fechado.

## Identidade visual (Vortex Marketplace)

Como o frontend agora é algo que uma pessoa de negócio realmente vê na tela,
troquei a marca padrão do Chainlit pela da empresa fictícia do projeto:

- `public/logo_dark.svg` / `public/logo_light.svg` / `public/favicon.svg`: ícone
  de vórtice/espiral + "Vortex Analytics Copilot", nas mesmas cores das
  apresentações HTML do projeto.
- [`chainlit.md`](../../../chainlit.md): tela de boas-vindas/Readme do app,
  explicando o que é a Vortex Marketplace, o que dá pra perguntar, e como o
  sistema funciona por trás.
- `.chainlit/config.toml`: nome do assistente trocado para "Vortex Analytics
  Copilot".
- [`scripts/api.py`](../../../scripts/api.py): título/descrição do Swagger
  também referenciam a Vortex Marketplace.

## Como rodar

```bash
# API (porta 8000)
docker compose exec app uvicorn api:app --host 0.0.0.0 --port 8000 --app-dir scripts

# Frontend Chainlit (porta 8001) - sem DATABASE_URL, ver nota do 6.3/6.4 acima
docker compose exec -e DATABASE_URL= app chainlit run scripts/chainlit_app.py --host 0.0.0.0 --port 8001
```

Depois, `http://localhost:8000/docs` (Swagger) e `http://localhost:8001`
(chat).

## O que ainda falta

- **Início automático:** hoje os dois processos (`uvicorn`, `chainlit run`)
  precisam ser subidos manualmente dentro do container a cada vez — o
  `Dockerfile` ainda só faz `sleep infinity`. Automatizar isso (CMD, ou um
  `docker-compose` com dois serviços) fica para fechar a entrega.
- **CORS:** a API não tem `CORSMiddleware` configurado ainda. Não dá problema
  hoje porque o Chainlit chama a API do lado do servidor (não do navegador),
  mas se um dia o frontend for separado (ex: hospedado estático, à parte da
  API), vai precisar.
- **Testes automatizados da API:** o que validei até aqui foi manual
  (Swagger, curl, chat) — ainda não escrevi um teste tipo `pytest` para os
  endpoints.
- **Hospedagem (E6 ainda em aberto):** decisão de onde a API e o frontend vão
  rodar em produção/demonstração (hoje só local, via Docker) ainda não foi
  tomada.
