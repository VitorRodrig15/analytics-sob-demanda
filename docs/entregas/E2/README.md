# E2 — Infraestrutura e Ingestão de Dados

**Período:** 26/10 a 30/10/2026 · **Foco:** Dados · **Status:** ✅ Concluída

Entregáveis 2.1 a 2.5: ambiente configurado, dados do Olist limpos e
carregados, dicionário semântico escrito e dividido em chunks, embeddings
gerados e gravados no pgvector, e tudo validado contra o banco real.

## 2.1 Ambiente de desenvolvimento

Dois containers Docker:
- `analytics_db`: PostgreSQL 16 com a extensão **pgvector 0.8.7**.
- `analytics_app`: Python 3.12 com LangGraph, FastAPI, psycopg, pandas e as
  bibliotecas da NVIDIA já instaladas.

A chave da NVIDIA fica num `.env` local, fora do Git (`.env.example` serve de
modelo). Ver `docker-compose.yml` e `Dockerfile` na raiz do projeto.

## 2.2 Pipeline de ingestão de dados

**Análise de qualidade antes de limpar** (`scripts/profile_data.py` →
[docs/a1_perfil_dados.md](../../a1_perfil_dados.md)): confirmou os dois
desafios já previstos na E1 e trouxe outros:

| Achado | Tratamento |
|---|---|
| Geolocalização: 1.000.163 linhas, das quais 261.831 duplicatas exatas; as 738.332 restantes são pontos geográficos distintos (um CEP de 5 dígitos cobre uma região, não um endereço único) | Agregada 1 linha por CEP (média de lat/lng) |
| 814 avaliações com `review_id` repetido | Chave composta (avaliação + pedido) |
| 2.965 pedidos sem data de entrega | Métricas de entrega consideram só pedidos `delivered` |
| 610 produtos sem categoria | Categoria `sem_categoria` |
| Set–out/2018 com só 20 pedidos | Dados confiáveis só até ago/2018 |
| 96,9% dos clientes compraram uma única vez | Definição de churn documentada explicitamente |

**Modelagem** (`sql/dw_schema.sql`): schema `dw` com 8 tabelas (as 5
mapeadas na E1 mais produtos, avaliações e geolocalização), coluna `region`
derivada do estado, tradução de categoria incorporada aos produtos, e a
geolocalização **sem chave estrangeira** (0,3% dos CEPs de clientes/vendedores
não existem nela — uma FK obrigatória descartaria esses registros).

**Limpeza e carga** (`scripts/load_dw.py`): transação única, idempotente —
**569.703 linhas** carregadas, sem perda de nenhuma linha de negócio.

## 2.3 Estratégia de chunking

**Dicionário semântico** (pasta [`knowledge/`](../../../knowledge/)):

| Arquivo | Conteúdo |
|---|---|
| `metricas.md` | 18 métricas, com sinônimos, fórmula, filtros e SQL de referência |
| `regras_negocio.md` | 13 regras (período dos dados, datas relativas, segurança, etc.) |
| `tabelas.md` | Descrição das 8 tabelas do schema `dw` |
| `exemplos_sql.json` | 22 pares pergunta → SQL, cobrindo as 4 intenções (agregação, comparação, tendência, ranking) |

Os 38 SQLs do dicionário são executados automaticamente contra o banco real
por `scripts/validate_knowledge.py` → [docs/b1_validacao_sql.md](../../b1_validacao_sql.md).

**Chunking** (`scripts/build_chunks.py` → [docs/b2_chunks.md](../../b2_chunks.md)):
**61 chunks**, um por unidade de significado (nunca por tamanho fixo), cada um
com um texto de busca (sem SQL) separado do conteúdo entregue ao agente (com
SQL). Maior chunk: 399 tokens, dentro do limite de 512.

## 2.4 Embeddings

Modelo de embedding originalmente previsto (`nv-embedqa-e5-v5`) foi
**descontinuado pela NVIDIA em 25/08/2026**. Testados os modelos disponíveis
com perguntas em português; escolhido `nvidia/nemotron-3.5-embed-1b`
(1024 dimensões — limite do índice HNSW do pgvector), com a mesma precisão do
modelo de 8B e 10× mais rápido.

`scripts/embed_chunks.py` grava os 61 chunks em `rag.documents`
(`sql/rag_schema.sql`), com metadados de fonte, tipo, tags e data.

## 2.5 Validação da ingestão

`scripts/validate_ingestion.py` → [docs/d1_validacao_ingestao.md](../../d1_validacao_ingestao.md):
**18 de 18 verificações aprovadas**, incluindo uma busca de teste com 12
perguntas em português (palavras diferentes das do dicionário) — **12/12**
encontraram o chunk certo entre os 3 primeiros resultados.

## Resumo técnico completo

Relatório consolidado desta entrega, com os comandos de reprodução passo a
passo: [docs/e2_planejamento_entrega.md](../../e2_planejamento_entrega.md).
