# E2 — Planejamento e registro da entrega

**Projeto:** Analytics sob Demanda (Data Q&A Copilot) · Vortex Marketplace  
**Entrega:** E2 — Infraestrutura e Ingestão de Dados

Este documento consolida o escopo planejado para a E2, as decisões de implementação, os recursos utilizados, os resultados obtidos e as validações realizadas. A entrega contempla os itens 2.1 a 2.5.

## 1. Objetivo e escopo

Preparar a infraestrutura de desenvolvimento e a base de dados que serão utilizadas pelas próximas etapas do projeto. Ao final da E2, os dados do Olist estão carregados e tratados no PostgreSQL, as definições de negócio estão documentadas e indexadas no pgvector, e os principais componentes da ingestão foram validados.

O fluxo implementado foi:

```text
CSVs do Olist → análise de qualidade → banco de dados (dw) → dicionário semântico
             → divisão em chunks → embeddings no pgvector (rag) → validação
```

O ambiente mantém duas áreas com responsabilidades distintas:

- **`dw`**: dados de negócio, como pedidos, clientes e vendas; fonte para consultas SQL e indicadores.
- **`rag`**: conhecimento semântico, como definições de métricas, regras, descrições de tabelas e exemplos SQL; fonte para recuperação contextual.

## 2. Entregável 2.1 — Ambiente de desenvolvimento

### Planejamento

Disponibilizar um ambiente reproduzível, compartilhado pela equipe e executado em containers, sem exigir instalação local do PostgreSQL e das bibliotecas da aplicação.

### Implementação e recursos utilizados

O projeto é executado em Docker Compose com dois containers:

- `analytics_db`: PostgreSQL 16 e extensão pgvector 0.8.7.
- `analytics_app`: Python 3.12, LangGraph, FastAPI, biblioteca da NVIDIA, pandas e drivers de banco.

A chave da API da NVIDIA é configurada em `.env`, arquivo que não deve ser versionado.

### Verificação

```bash
docker compose ps
```

Verificação da extensão no PostgreSQL:

```sql
SELECT extname, extversion FROM pg_extension;
```

Resultado esperado: extensão `vector` na versão `0.8.7`.

## 3. Entregável 2.2 — Pipeline de ingestão de dados

### 3.1 Análise de qualidade

Foi criado um perfil dos 9 arquivos CSV, incluindo volume, tipos, valores ausentes, duplicidades e relações entre tabelas. Os resultados estão registrados em `docs/a1_perfil_dados.md`.

| Problema identificado | Tratamento aplicado |
|---|---|
| Geolocalização: 1.000.163 linhas, das quais 261.831 são duplicatas exatas; as 738.332 restantes são pontos geográficos distintos (em média 38,8 por CEP, pois um CEP de 5 dígitos cobre uma região inteira, não um endereço único) | Agregada uma linha por CEP (média de lat/lng), para evitar multiplicação de pedidos em cruzamentos |
| 814 avaliações com ID repetido | Utilizada chave composta por avaliação e pedido |
| 2.965 pedidos sem data de entrega | Métricas de entrega consideram apenas pedidos entregues |
| 610 produtos sem categoria | Categoria preenchida como `sem_categoria` |
| Set–out/2018 com apenas 20 pedidos | Dados considerados confiáveis até ago/2018 |
| 96,9% dos clientes compraram uma única vez | Definição de churn documentada explicitamente |

### 3.2 Modelagem

Foram definidas 8 tabelas no schema `dw`, com tipos de dados, chaves e relações explícitas. Duas adaptações simplificam as consultas futuras:

- A coluna **região** (Norte, Nordeste etc.) é derivada do estado.
- A categoria traduzida é armazenada na tabela de produtos para evitar um JOIN adicional.

### 3.3 Limpeza e carga

O script `load_dw.py` aplica as regras de tratamento e carrega as 8 tabelas, totalizando **569.703 linhas**. A operação pode ser repetida sem duplicar dados e utiliza transação para evitar cargas parcialmente aplicadas em caso de erro.

Consulta usada para verificar dados carregados e relações entre tabelas:

```sql
SELECT c.customer_region AS regiao,
       COUNT(DISTINCT o.order_id) AS pedidos,
       ROUND(SUM(oi.price), 2)    AS receita
FROM dw.orders o
JOIN dw.customers c    ON c.customer_id = o.customer_id
JOIN dw.order_items oi ON oi.order_id = o.order_id
WHERE o.order_status = 'delivered'
  AND o.order_purchase_timestamp < '2018-09-01'
GROUP BY c.customer_region
ORDER BY receita DESC;
```

## 4. Entregável 2.3 — Dicionário semântico e estratégia de chunking

### Conteúdo preparado

Os documentos de conhecimento ficam na pasta `knowledge/`:

| Arquivo             | Conteúdo                                                                 |
| `metricas.md`       | 18 métricas com definição, fórmula, filtros e SQL de referência          |
| `regras_negocio.md` | 13 regras, incluindo período dos dados, contagem de clientes e segurança |
| `tabelas.md`        | Descrição das 8 tabelas e respectivas colunas                            |
| `exemplos_sql.json` | 22 exemplos de perguntas e SQL correspondente                            |

Os **38 SQLs** do dicionário foram executados automaticamente para verificar sua validade. A margem de contribuição está documentada como não disponível porque o dataset não contém custos dos produtos. O churn de vendedores está definido nos exemplos; seu valor observado foi 32,7% no último trimestre considerado.

### Estratégia e resultado do chunking

Foi escolhida a divisão por unidade de significado, mantendo cada métrica, regra, tabela ou exemplo completo em um chunk. Essa abordagem evita separar definições, filtros e SQLs, como poderia ocorrer com cortes por número de caracteres ou por parágrafo.

O resultado foi de **61 chunks**, cada um com:

- **Texto de busca:** texto sem SQL, formulado para facilitar a recuperação a partir de perguntas.
- **Conteúdo:** informação completa, incluindo SQL quando aplicável.

O maior chunk tem **399 tokens**, abaixo do limite de 512. O documento `docs/b2_chunks.md` registra os detalhes e um exemplo de chunk.

## 5. Entregável 2.4 — Embeddings no pgvector

Cada chunk é representado por um vetor numérico para permitir a recuperação de conteúdos semanticamente próximos. Os **61 embeddings** foram gerados com um modelo da NVIDIA e gravados em `rag.documents`, acompanhados pelos metadados de fonte, tipo, data e tags.

### Decisões técnicas

- O modelo inicialmente planejado, `nv-embedqa-e5-v5`, foi descontinuado pela NVIDIA em 25/08/2026.
- Foram comparados modelos disponíveis usando perguntas em português:

| Modelo | Acertos no teste | Tempo |
|---|---:|---:|
| `nemotron-3.5-embed-1b` (selecionado) | 3 de 3 | 1,8 s |
| `nemotron-3.5-embed-8b` | 3 de 3 | 19,2 s |

- Foi adotada dimensão de **1024** em vez de 2048, pois o índice de busca rápida do pgvector aceita até 2000 dimensões. A precisão observada no teste foi mantida.
- Cada registro guarda o nome do modelo utilizado para rastrear a origem dos embeddings.

Consultas para verificar tipos de documentos e dimensões dos vetores:

```sql
SELECT doc_type, COUNT(*) AS chunks, MIN(vector_dims(embedding)) AS dimensoes
FROM rag.documents
GROUP BY doc_type;

SELECT id, LEFT(embedding::text, 100) || '...' AS inicio_do_vetor
FROM rag.documents
WHERE id = 'metric:ticket-medio';
```

## 6. Entregável 2.5 — Validação da ingestão

O script abaixo reúne as verificações de infraestrutura, carga, vetores, índice e recuperação:

```bash
docker compose exec app python scripts/validate_ingestion.py
```

| Verificação | Resultado registrado |
|---|---|
| PostgreSQL e pgvector ativos | Aprovada |
| 8 tabelas do `dw` com o número de linhas esperado | Aprovada |
| 61 chunks no banco vetorial, todos com vetor de 1024 dimensões | Aprovada |
| Índice HNSW criado | Aprovada |
| Busca: informação correta entre os 3 primeiros resultados | 12 de 12; 10 em primeiro lugar |
| **Total** | **18 de 18 verificações** |

As 12 consultas de busca foram formuladas com palavras diferentes das usadas no dicionário, para verificar recuperação por significado. Exemplos:

| Consulta de teste | Conteúdo recuperado |
|---|---|
| “Qual o valor médio gasto em cada compra?” | Ticket médio |
| “Como contar clientes sem repetir a mesma pessoa?” | Clientes únicos |
| “A consulta pode apagar ou alterar dados?” | Regra de segurança |

Comando para reproduzir uma busca:

```bash
docker compose exec app python scripts/search.py "Qual foi a taxa de churn de vendedores por região no último trimestre?"
```

Os três primeiros resultados observados foram:

```text
#  similaridade  tipo           titulo
1  0.599         sql_example    Qual foi a taxa de churn de vendedores por região no último trimestre?
2  0.568         metric         Churn de vendedores
3  0.482         sql_example    Qual foi a taxa de churn por região no último trimestre?
```

Uma pergunta pode ser alterada no comando para repetir o teste. A opção `--conteudo` inclui o conteúdo completo dos chunks nos resultados. A recuperação dos três primeiros itens permite reunir conhecimentos complementares, como métrica, regra e tabela.

## 7. Situação da entrega e continuidade

| Entregável | Status |
|---|---|
| 2.1 Ambiente configurado | Concluído |
| 2.2 Pipeline de ingestão | Concluído |
| 2.3 Estratégia de chunking | Concluído |
| 2.4 Embeddings no pgvector | Concluído |
| 2.5 Validação da ingestão | Concluído |

**Pendência anterior à E2:** criação do repositório GitHub (entregável 1.5). A estrutura de pastas está definida, e o `.gitignore` protege a chave da API e os CSVs, cuja redistribuição não é permitida pelo Kaggle.

**Próxima etapa — E3, Pipeline RAG:**

- Conectar o LLM GPT-OSS-20B pela NVIDIA, já confirmado como disponível com a chave utilizada.
- Implementar o fluxo de pergunta, recuperação de chunks e geração de SQL pelo LLM.
- Testar o fluxo com as perguntas de exemplo do dicionário.

## 8. Indicadores de referência

| Indicador | Valor |
|---|---:|
| Pedidos | 99.441 (set/2016 a out/2018; dados confiáveis até ago/2018) |
| Clientes reais | 96.096 |
| Vendedores | 3.095 (95,5% no Sudeste e no Sul) |
| Receita jan–ago/2018 | R$ 7,22 milhões |
| Ticket médio 2018 | R$ 136,75 |
| Entregas no prazo em 2018 | 92,3% |
| Churn de clientes (jun–ago/2018) | 99,3% (compra única) |
| Churn de vendedores (jun–ago/2018) | 32,7% |
| Taxa de recompra | 3,0% |

## 9. Decisões e limitações registradas

- **Dados transacionais no `dw`, conhecimento no `rag`:** a busca vetorial recupera definições e contexto; valores de negócio são calculados por consultas SQL sobre os dados.
- **Geolocalização:** 0,3% dos CEPs dos clientes não estão presentes na tabela. A orientação é relacionar por CEP usando `LEFT JOIN`, sem descartar esses clientes.
- **Churn de clientes:** o valor de 99% reflete que 96,9% dos clientes fizeram uma única compra. A definição está explícita no dicionário; churn de vendedores também é acompanhado como indicador.
- **Atualização do conhecimento:** `validate_knowledge.py` valida os SQLs, `build_chunks.py` reconstrói os chunks e `embed_chunks.py` recria os embeddings. Os scripts podem ser executados novamente sem duplicar registros.
- **Segurança das consultas:** a regra de somente leitura está documentada e as validações atuais executam consultas em modo somente leitura. Nas próximas entregas, o agente validador deverá bloquear comandos diferentes de `SELECT`.
- **Orquestração:** a decisão da E1 foi usar LangGraph para controlar o fluxo de recuperação, geração, validação e correção do SQL.
