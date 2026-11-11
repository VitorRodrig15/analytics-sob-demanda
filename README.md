# Analytics sob Demanda — Data Q&A Copilot

Sistema multi-agente de analytics conversacional com RAG, desenvolvido para o
**Plano de Treinamento Técnico Corporativo** da DELL ("Designing Multi-Agent
Systems", de Victor Dibia). Projeto: **Analytics sob Demanda (Business Data Q&A)**.

**Início:** 22/10/2026 · **Status:** em desenvolvimento

## O problema de negócio

A **Vortex Marketplace**, um marketplace B2C brasileiro fictício (8.000
vendedores, 120.000 pedidos/mês), depende hoje do time de BI para qualquer
análise fora dos dashboards prontos. O time recebe 60+ solicitações ad-hoc por
semana, com 15 dias de espera média, e diferentes analistas calculam métricas
como *ticket médio* e *churn* de formas divergentes.

O objetivo deste projeto é construir um **Copilot de Analytics** que permita a
um gestor de negócio perguntar em linguagem natural (ex.: *"qual a taxa de
churn de vendedores por região no último trimestre?"*) e receber uma resposta
correta, com a métrica calculada de forma consistente e a visualização certa —
sem escrever SQL.

## A solução: 5 agentes especializados + RAG

| Agente | Responsabilidade |
|---|---|
| **Orquestrador** | Recebe a pergunta, identifica a intenção e coordena o fluxo |
| **Semântico / RAG** | Busca no banco vetorial as definições oficiais de métricas, tabelas e exemplos de SQL |
| **Gerador de SQL** | Traduz a intenção + contexto do RAG em uma query SQL segura |
| **Validador e Segurança** | Garante que a query é somente leitura, sem riscos de injeção |
| **Execução e Resposta** | Roda a query, formata a visualização e escreve a narrativa |

O fluxo é um **workflow condicional com loop de correção**: se o SQL falhar na
validação ou na execução, o erro volta para o Gerador de SQL corrigir, em vez
de o sistema simplesmente falhar.

## Stack técnico

| Camada | Tecnologia | Por quê (resumo — detalhes no [README da E1](docs/entregas/E1/README.md)) |
|---|---|---|
| Orquestração de agentes | **LangGraph** | Fluxo precisa ser controlado passo a passo, com loop de correção explícito — não autonomia aberta entre agentes |
| Dados + banco vetorial | **PostgreSQL + pgvector** | Dados de negócio e embeddings no mesmo banco, simplificando a infraestrutura |
| LLM | **GPT-OSS-20B**, via NVIDIA NIM | Modelo de raciocínio aberto, acessível pela API da NVIDIA |
| Embeddings | **NVIDIA NIM** (`nemotron-3.5-embed-1b`, 1024 dim) | O modelo originalmente previsto foi descontinuado em 25/08/2026; este foi escolhido após teste comparativo — ver [E2](docs/entregas/E2/README.md) |
| API | **FastAPI** | Recebe a pergunta, orquestra os agentes, devolve a resposta |
| Ambiente | **Docker** (PostgreSQL + Python) | Ambiente reprodutível, sem instalação manual |

## Dataset

**Olist Brazilian E-Commerce** (Kaggle), 2016–2018: 99.441 pedidos reais de um
marketplace brasileiro, em 9 tabelas relacionais. Simula bem o cenário da
Vortex. Detalhes da análise de qualidade e da limpeza em
[docs/entregas/E2](docs/entregas/E2/README.md).

> Os arquivos brutos **não estão neste repositório** (o Kaggle não permite
> redistribuição). Veja [Como rodar o projeto](#como-rodar-o-projeto) para
> baixá-los.

## Entregas semanais

O projeto segue um cronograma de 7 entregas evolutivas + apresentação final
(22/10 a 12/12). Cada entrega concluída tem uma pasta própria em
`docs/entregas/`, com o relatório da semana e as evidências (relatórios
gerados, exemplos de execução, prints de resultado).

| # | Entrega | Período | Status | Pasta |
|---|---|---|---|---|
| E1 | Planejamento e Design do Sistema | 22/10 – 24/10 | ✅ Concluída | [docs/entregas/E1](docs/entregas/E1/README.md) |
| E2 | Infraestrutura e Ingestão de Dados | 27/10 – 31/10 | ✅ Concluída | [docs/entregas/E2](docs/entregas/E2/README.md) |
| E3 | Pipeline RAG Funcional | 03/11 – 07/11 | ✅ Concluída | [docs/entregas/E3](docs/entregas/E3/README.md) |
| E4 | Primeiro Agente Funcional | 10/11 – 14/11 | ✅ Concluída | [docs/entregas/E4](docs/entregas/E4/README.md) |
| E5 | Sistema Multi-Agente Orquestrado | 17/11 – 21/11 | ⏳ Em breve | — |
| E6 | API e Interface do Usuário | 24/11 – 28/11 | ⏳ Em breve | — |
| E7 | Testes, Avaliação e Documentação | 01/12 – 05/12 | ⏳ Em breve | — |
| — | Apresentação Final | 08/12 – 12/12 | ⏳ Em breve | — |

## Estrutura do repositório

```
├── docker-compose.yml, Dockerfile   → ambiente (PostgreSQL + pgvector + Python)
├── requirements.txt                 → dependências Python
├── sql/                             → scripts SQL dos schemas dw (dados) e rag (conhecimento)
├── knowledge/                       → dicionário semântico (métricas, regras, tabelas, exemplos de SQL)
├── scripts/                         → pipeline completo: ingestão, chunking, embeddings, RAG, testes
├── docs/                            → relatórios gerados pelos scripts + pasta entregas/ com o histórico semanal
└── data/                            → dados brutos e processados (fora do Git, ver .gitignore)
```

## Como rodar o projeto

**1. Pré-requisitos:** Docker Desktop e uma chave de API da NVIDIA (gratuita em
[build.nvidia.com](https://build.nvidia.com)).

**2. Configurar o ambiente:**

```bash
copy .env.example .env
# edite o .env e cole a sua NVIDIA_API_KEY
docker compose up -d
```

**3. Baixar o dataset** (requer conta no Kaggle):

```python
import kagglehub
path = kagglehub.dataset_download("olistbr/brazilian-ecommerce")
```

Copie os CSVs extraídos para `data/raw/olist/`.

**4. Rodar o pipeline completo**, na ordem (detalhes de cada passo nos READMEs
de cada entrega):

```bash
docker compose exec app python scripts/profile_data.py        # E2 — perfil de qualidade
docker compose exec app python scripts/load_dw.py              # E2 — limpeza e carga
docker compose exec app python scripts/validate_knowledge.py   # E2 — valida os SQLs do dicionário
docker compose exec app python scripts/build_chunks.py         # E2 — divide o dicionário em chunks
docker compose exec app python scripts/embed_chunks.py         # E2 — gera os embeddings
docker compose exec app python scripts/validate_ingestion.py   # E2 — valida a ingestão
docker compose exec app python scripts/rag_pipeline.py "qual o ticket médio?"  # E3 — pergunta ao pipeline RAG
docker compose exec app python scripts/agent.py "qual foi a receita de 2017?" # E4 — pergunta ao agente com tools
```

> A chamada à LLM (`rag_pipeline.py`) leva entre 130 e 180 segundos por
> pergunta — é uma limitação do tier gratuito da NVIDIA, documentada em
> [docs/entregas/E3](docs/entregas/E3/README.md).

## Segurança e dados sensíveis

- A chave da API da NVIDIA fica só no `.env` local, **fora do Git** (veja
  `.env.example` para o modelo sem os valores).
- Os CSVs brutos do Olist (`data/raw/`) e os arquivos gerados (`data/processed/`)
  também ficam fora do Git — por licença do Kaggle e por serem reproduzíveis a
  partir do pipeline.
- Nenhum dado pessoal real está envolvido: o Olist já é um dataset público e
  anonimizado.
