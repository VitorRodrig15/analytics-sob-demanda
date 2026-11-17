# E5 — Sistema Multi-Agente Orquestrado — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir o agente único da E4 por 5 agentes especializados (Orquestrador, Semântico/RAG, Gerador de SQL, Validador e Segurança, Execução e Resposta), orquestrados por um grafo LangGraph com estado compartilhado e loop de correção, testados individualmente e em conjunto.

**Architecture:** Cada agente é uma função Python pura ou com uma chamada de LLM, num arquivo próprio em `scripts/`, lendo e devolvendo campos de um `AgentContext` compartilhado (dataclass). `scripts/grafo.py` monta um `StateGraph` do LangGraph ligando os 5 nós com arestas condicionais (funções puras de roteamento, testáveis sem LLM). O Validador usa `sqlglot` para análise estática real da árvore SQL, sem LLM.

**Tech Stack:** Python, LangGraph (`langgraph.graph.StateGraph`), `sqlglot` (novo), `openai` (cliente NVIDIA NIM, já em uso), `pytest` (novo, só para as partes determinísticas), Postgres via `psycopg` (reaproveitado de `tools.py`).

**Spec:** [docs/entregas/E5/design.md](../../entregas/E5/design.md)

## Global Constraints

- Latência: ~130-180s por chamada de LLM (fila do tier gratuito da NVIDIA) — cada chamada ao Orquestrador, Gerador de SQL ou Execução/Resposta custa isso, não importa o tamanho da pergunta.
- `MAX_TENTATIVAS = 3`, contador **único** em `AgentContext.tentativas`, compartilhado entre o loop do Validador e o loop de erro de execução.
- Nenhuma operação de escrita em nenhuma camada (nem o Gerador de SQL deve considerar isso uma opção).
- A role `agente_leitura` (somente leitura, `sql/agent_readonly_role.sql`) continua sendo a conexão usada para rodar qualquer SQL — defesa em profundidade, mesmo com o Validador.
- Respostas sempre em português do Brasil, valores em R$ com 2 casas, citando a fonte da definição usada no formato `(fonte: <título>)`.
- Testes rodam contra a LLM de verdade (nunca mock) — mesmo padrão de E1 a E4 — com baterias pequenas e curadas, em segundo plano.
- "Execução e Resposta" é **um** agente só (não dividir em dois nós) — fiel à arquitetura da E1.
- Toda rota do grafo termina no nó `execucao_resposta`, que é sempre quem escreve o texto final.

## Review Focus

- Validador recebe SQL sintaticamente malformado (erro de parsing do `sqlglot`, não uma regra de negócio violada) — deve devolver `ValidacaoResultado(ok=False, motivo=...)`, nunca deixar a exceção subir e quebrar o grafo.
- As tentativas de correção se esgotam (Validador rejeita 3x, ou execução falha 3x) — o grafo precisa terminar graciosamente em `execucao_resposta` explicando o que não foi possível responder, não travar nem lançar exceção.
- `consulta_banco`/execução real devolve 0 linhas (consulta válida, sem dados para o filtro) — a resposta final deve dizer que não há resultado, não inventar um número nem quebrar ao formatar.
- O Orquestrador classifica errado uma pergunta que só pede definição (ex.: "o que é ticket médio?") como se precisasse de SQL — o roteamento do caminho "definicao" deve pular estritamente o Gerador de SQL e a execução.
- A resposta de classificação do LLM no Orquestrador vem com o artefato de canal do GPT-OSS colado (ex. `dado<|channel|>commentary`), o mesmo bug já visto no nome de tool na E4 — precisa da mesma limpeza (`split("<|")[0]`) aplicada à intenção extraída.

---

## Task 1: Estado compartilhado (`AgentContext`)

**Files:**
- Create: `scripts/state.py`
- Test: `tests/test_state.py`

**Interfaces:**
- Produces: `AgentContext` (dataclass) com os campos: `pergunta: str`, `intencao: str | None = None`, `contexto_rag: list[dict] = field(default_factory=list)`, `sql_gerado: str | None = None`, `validacao_ok: bool | None = None`, `motivo_rejeicao: str | None = None`, `resultado_execucao: dict | None = None`, `erro_execucao: str | None = None`, `resposta_final: str = ""`, `tentativas: int = 0`, `historico: list[str] = field(default_factory=list)`. Método `registrar(self, evento: str) -> None` que faz `self.historico.append(evento)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_state.py
from scripts.state import AgentContext

def test_agent_context_defaults():
    ctx = AgentContext(pergunta="qual a receita de 2017?")
    assert ctx.pergunta == "qual a receita de 2017?"
    assert ctx.intencao is None
    assert ctx.contexto_rag == []
    assert ctx.tentativas == 0
    assert ctx.historico == []

def test_agent_context_registrar_evento():
    ctx = AgentContext(pergunta="x")
    ctx.registrar("orquestrador: intencao=dado")
    ctx.registrar("gerador_sql: sql gerado")
    assert ctx.historico == ["orquestrador: intencao=dado", "gerador_sql: sql gerado"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec app pytest tests/test_state.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'scripts.state'`

- [ ] **Step 3: Implement `AgentContext` em `scripts/state.py`**

Dataclass com os campos e o método `registrar` listados acima.

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec app pytest tests/test_state.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/state.py tests/test_state.py
git commit -m "E5: adiciona AgentContext, o estado compartilhado entre os agentes"
```

---

## Task 2: Validador e Segurança (determinístico, `sqlglot`)

**Files:**
- Create: `scripts/validador.py`
- Modify: `requirements.txt` (adicionar `sqlglot>=25` e `pytest>=8` nas seções apropriadas)
- Test: `tests/test_validador.py`

**Interfaces:**
- Consumes: nada de outros agentes — função pura sobre uma string SQL.
- Produces: `ValidacaoResultado` (dataclass: `ok: bool`, `motivo: str | None = None`) e `validar_sql(sql: str) -> ValidacaoResultado` em `scripts/validador.py`. `motivo_rejeicao` do `AgentContext` (Task 1) recebe `resultado.motivo` quando `ok=False`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_validador.py
from scripts.validador import validar_sql

def test_aceita_select_simples_no_schema_dw():
    r = validar_sql("SELECT order_id FROM dw.orders LIMIT 10")
    assert r.ok is True

def test_aceita_with_select_no_schema_dw():
    r = validar_sql("WITH t AS (SELECT * FROM dw.orders) SELECT * FROM t")
    assert r.ok is True

def test_aceita_ponto_e_virgula_dentro_de_string_literal():
    # a regra antiga da E4 (tools.py) rejeitava isso por conter ";" no texto -
    # o sqlglot entende que e so um literal, nao um separador de statement
    sql = "SELECT * FROM dw.order_reviews WHERE review_comment_message = 'Otimo; recomendo'"
    r = validar_sql(sql)
    assert r.ok is True

def test_rejeita_insert():
    r = validar_sql("INSERT INTO dw.orders (order_id) VALUES ('x')")
    assert r.ok is False
    assert r.motivo

def test_rejeita_multiplas_instrucoes():
    r = validar_sql("SELECT * FROM dw.orders; DROP TABLE dw.orders")
    assert r.ok is False

def test_rejeita_tabela_fora_do_schema_dw():
    r = validar_sql("SELECT * FROM rag.chunks")
    assert r.ok is False

def test_rejeita_sql_sintaticamente_invalido_sem_lancar_excecao():
    r = validar_sql("SELECT FROM WHERE dw.orders")
    assert r.ok is False
    assert r.motivo
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec app pytest tests/test_validador.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'scripts.validador'`

- [ ] **Step 3: Adicionar `sqlglot>=25` e `pytest>=8` ao `requirements.txt`**

Adicionar na seção "Banco / PG Vector" (ou numa nova seção "Validacao e testes") do `requirements.txt` existente.

- [ ] **Step 4: Implementar `validar_sql(sql: str) -> ValidacaoResultado` em `scripts/validador.py`**

Usar `sqlglot.parse(sql, read="postgres")` dentro de um `try/except sqlglot.errors.ParseError` (erro de parsing vira `ValicaoResultado(ok=False, motivo="SQL invalido: ...")`). Regras, na ordem: (1) exatamente um statement; (2) o statement (ou o `SELECT` interno de um `WITH`) é do tipo `exp.Select`, nada de `exp.Insert`/`exp.Update`/`exp.Delete`/`exp.Drop`/outros; (3) toda tabela referenciada (`statement.find_all(exp.Table)`) tem `table.db == "dw"`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose exec app pytest tests/test_validador.py -v`
Expected: PASS (7 passed)

- [ ] **Step 6: Commit**

```bash
git add scripts/validador.py requirements.txt tests/test_validador.py
git commit -m "E5: Validador e Seguranca deterministico com sqlglot"
```

---

## Task 3: Funções de roteamento do grafo (arestas condicionais)

**Files:**
- Create: `scripts/grafo_routing.py`
- Test: `tests/test_grafo_routing.py`

**Interfaces:**
- Consumes: `AgentContext` (Task 1).
- Produces, em `scripts/grafo_routing.py`:
  - `rotear_apos_orquestrador(ctx: AgentContext) -> str` → `"esclarecimento"` ou `"com_contexto"` (`ctx.intencao == "esclarecimento"` → primeiro; qualquer outro valor → segundo).
  - `rotear_apos_semantico(ctx: AgentContext) -> str` → `"definicao"` (`ctx.intencao == "definicao"`) ou `"gerar_sql"` (qualquer outro).
  - `rotear_apos_validador(ctx: AgentContext) -> str` → `"executar"` (`ctx.validacao_ok is True`) ou, se `ctx.validacao_ok is False`: `"tentar_de_novo"` se `ctx.tentativas < 3`, senão `"esgotado"`.
  - `rotear_apos_execucao(ctx: AgentContext) -> str` → `"ok"` se `ctx.erro_execucao is None`; senão `"tentar_de_novo"` se `ctx.tentativas < 3`, senão `"esgotado"`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_grafo_routing.py
from scripts.state import AgentContext
from scripts.grafo_routing import (
    rotear_apos_orquestrador, rotear_apos_semantico,
    rotear_apos_validador, rotear_apos_execucao,
)

def test_rotear_apos_orquestrador_esclarecimento():
    ctx = AgentContext(pergunta="x", intencao="esclarecimento")
    assert rotear_apos_orquestrador(ctx) == "esclarecimento"

def test_rotear_apos_orquestrador_segue_fluxo():
    for intencao in ("definicao", "dado", "ambas"):
        ctx = AgentContext(pergunta="x", intencao=intencao)
        assert rotear_apos_orquestrador(ctx) == "com_contexto"

def test_rotear_apos_semantico_definicao_pula_sql():
    ctx = AgentContext(pergunta="x", intencao="definicao")
    assert rotear_apos_semantico(ctx) == "definicao"

def test_rotear_apos_semantico_dado_vai_pro_gerador():
    ctx = AgentContext(pergunta="x", intencao="dado")
    assert rotear_apos_semantico(ctx) == "gerar_sql"

def test_rotear_apos_validador_aprovado():
    ctx = AgentContext(pergunta="x", validacao_ok=True)
    assert rotear_apos_validador(ctx) == "executar"

def test_rotear_apos_validador_reprovado_tenta_de_novo():
    ctx = AgentContext(pergunta="x", validacao_ok=False, tentativas=1)
    assert rotear_apos_validador(ctx) == "tentar_de_novo"

def test_rotear_apos_validador_reprovado_esgota_tentativas():
    ctx = AgentContext(pergunta="x", validacao_ok=False, tentativas=3)
    assert rotear_apos_validador(ctx) == "esgotado"

def test_rotear_apos_execucao_sucesso():
    ctx = AgentContext(pergunta="x", erro_execucao=None)
    assert rotear_apos_execucao(ctx) == "ok"

def test_rotear_apos_execucao_erro_tenta_de_novo():
    ctx = AgentContext(pergunta="x", erro_execucao="coluna invalida", tentativas=2)
    assert rotear_apos_execucao(ctx) == "tentar_de_novo"

def test_rotear_apos_execucao_erro_esgota_tentativas():
    ctx = AgentContext(pergunta="x", erro_execucao="coluna invalida", tentativas=3)
    assert rotear_apos_execucao(ctx) == "esgotado"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec app pytest tests/test_grafo_routing.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'scripts.grafo_routing'`

- [ ] **Step 3: Implementar as 4 funções em `scripts/grafo_routing.py`**

Cada uma é um `if`/`return` direto sobre os campos do `AgentContext`, conforme descrito no bloco Interfaces acima. `MAX_TENTATIVAS = 3` como constante do módulo.

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec app pytest tests/test_grafo_routing.py -v`
Expected: PASS (10 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/grafo_routing.py tests/test_grafo_routing.py
git commit -m "E5: funcoes de roteamento do grafo (arestas condicionais), testadas sem LLM"
```

---

## Task 4: Agente Semântico/RAG (envelopa `busca_vetorial`)

**Files:**
- Create: `scripts/semantico_rag.py`

**Interfaces:**
- Consumes: `tool_busca_vetorial(pergunta: str, k: int = 3) -> str` (JSON, já existe em `scripts/tools.py`).
- Produces: `buscar_contexto(pergunta: str, k: int = 3) -> list[dict]` em `scripts/semantico_rag.py` — chama `tool_busca_vetorial`, faz `json.loads` do resultado e devolve a lista já parseada (mesmo formato de item: `{"fonte", "tipo", "similaridade", "conteudo"}`), para popular `AgentContext.contexto_rag` diretamente.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_semantico_rag.py
from unittest.mock import patch
from scripts.semantico_rag import buscar_contexto

def test_buscar_contexto_parseia_json_da_tool():
    fake_json = '[{"fonte": "Ticket medio", "tipo": "metrica", "similaridade": 0.9, "conteudo": "..."}]'
    with patch("scripts.semantico_rag.tool_busca_vetorial", return_value=fake_json) as mocked:
        resultado = buscar_contexto("qual o ticket medio?", k=3)
    mocked.assert_called_once_with("qual o ticket medio?", 3)
    assert resultado == [{"fonte": "Ticket medio", "tipo": "metrica", "similaridade": 0.9, "conteudo": "..."}]
```

Nota: este é o único teste do plano que faz mock — não do LLM (não há LLM aqui), só da chamada de rede/banco dentro de `tool_busca_vetorial`, pra testar unicamente o parsing do JSON. Consistente com a decisão de não mockar LLM.

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec app pytest tests/test_semantico_rag.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'scripts.semantico_rag'`

- [ ] **Step 3: Implementar `buscar_contexto` em `scripts/semantico_rag.py`**

Importa `tool_busca_vetorial` de `scripts.tools`, chama e faz `json.loads` do retorno.

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec app pytest tests/test_semantico_rag.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/semantico_rag.py tests/test_semantico_rag.py
git commit -m "E5: Agente Semantico/RAG como no do grafo, reaproveitando busca_vetorial"
```

---

## Task 5: Agente Orquestrador

**Files:**
- Create: `scripts/orquestrador.py`

**Interfaces:**
- Consumes: `OpenAI` client (já usado em `scripts/agent.py`), `LLM_MODEL`/`NVIDIA_BASE_URL` (mesmas env vars de `agent.py`).
- Produces: `classificar_intencao(pergunta: str, client: OpenAI) -> str` em `scripts/orquestrador.py`, devolvendo um entre `"definicao"`, `"dado"`, `"ambas"`, `"esclarecimento"`.

- [ ] **Step 1: Implementar `ORQUESTRADOR_SYSTEM_PROMPT` e `classificar_intencao` em `scripts/orquestrador.py`**

Prompt curto, só com a tarefa de classificação (contexto da Vortex Marketplace em 1-2 frases, as 4 categorias com 1 exemplo cada, instrução de responder só com a palavra da categoria). Chamada ao `client.chat.completions.create` sem `tools`, `max_tokens` baixo (ex. 20), `temperature=0`. Extrai `message.content`, aplica `.strip().lower().split("<|")[0]` (mesma limpeza do artefato de canal da E4) e valida contra as 4 categorias conhecidas; se vier algo fora delas, cai em `"ambas"` como padrão seguro (preferir buscar contexto e tentar dado a arriscar não responder nada).

- [ ] **Step 2: Verificação manual com chamada real (sem pytest — ver Task 8)**

Esta etapa não tem teste automatizado aqui porque usa a LLM de verdade (~130-180s por chamada) — a prova de que funciona isolado é a bateria da Task 8 (5.1). Ainda assim, rode uma vez agora pra confirmar antes de seguir:

```bash
docker compose exec app python -c "
from openai import OpenAI
import os
from scripts.orquestrador import classificar_intencao
client = OpenAI(base_url=os.getenv('NVIDIA_BASE_URL', 'https://integrate.api.nvidia.com/v1'), api_key=os.environ['NVIDIA_API_KEY'])
print(classificar_intencao('o que e ticket medio?', client))
"
```
Expected: imprime `definicao` (ou outra categoria plausível — confirme manualmente que faz sentido para a pergunta).

- [ ] **Step 3: Commit**

```bash
git add scripts/orquestrador.py
git commit -m "E5: Agente Orquestrador, classifica a intencao da pergunta"
```

---

## Task 6: Agente Gerador de SQL

**Files:**
- Create: `scripts/gerador_sql.py`

**Interfaces:**
- Consumes: `OpenAI` client; `ctx.contexto_rag: list[dict]` (Task 4); `ctx.motivo_rejeicao: str | None` / `ctx.erro_execucao: str | None` (Task 1).
- Produces: `gerar_sql(pergunta: str, contexto_rag: list[dict], erro_anterior: str | None, client: OpenAI) -> str` em `scripts/gerador_sql.py`, devolvendo só a string do SQL (sem crases, sem comentário).

- [ ] **Step 1: Implementar `GERADOR_SQL_SYSTEM_PROMPT` e `gerar_sql` em `scripts/gerador_sql.py`**

Prompt focado: recebe a pergunta e o `contexto_rag` formatado (fonte + conteúdo de cada chunk), instrução de escrever **só** um `SELECT`/`WITH` no schema `dw`, data de referência fixa `2018-08-31` (mesmo fato fixo do `AGENT_SYSTEM_PROMPT` da E4), regra de `dw.customers`/`dw.sellers` para região/cidade/estado (regra 8 da E4). Se `erro_anterior` não for `None`, inclui no prompt do usuário: "A tentativa anterior falhou por: {erro_anterior}. Corrija.". Extrai `message.content`, remove cercas de código markdown (` ```sql ` / ` ``` `) se vierem, e `.strip()`.

- [ ] **Step 2: Verificação manual com chamada real**

```bash
docker compose exec app python -c "
from openai import OpenAI
import os
from scripts.gerador_sql import gerar_sql
client = OpenAI(base_url=os.getenv('NVIDIA_BASE_URL', 'https://integrate.api.nvidia.com/v1'), api_key=os.environ['NVIDIA_API_KEY'])
contexto = [{'fonte': 'Receita', 'tipo': 'metrica', 'conteudo': 'Receita = soma de price em order_items de pedidos delivered.'}]
print(gerar_sql('qual foi a receita de 2017?', contexto, None, client))
"
```
Expected: imprime um `SELECT ... FROM dw.orders JOIN dw.order_items ...` plausível, sem crases markdown.

- [ ] **Step 3: Commit**

```bash
git add scripts/gerador_sql.py
git commit -m "E5: Agente Gerador de SQL"
```

---

## Task 7: Agente Execução e Resposta

**Files:**
- Create: `scripts/execucao_resposta.py`

**Interfaces:**
- Consumes: `agent_database_url()` e o padrão de execução de `tool_consulta_banco` (`scripts/tools.py`, reaproveitar a conexão `psycopg` com `conn.read_only = True` e o `LIMIT 50`); `OpenAI` client; `AgentContext` (Task 1).
- Produces, em `scripts/execucao_resposta.py`:
  - `executar_sql(sql: str) -> tuple[dict | None, str | None]` → `(resultado, None)` em caso de sucesso (`resultado = {"colunas": [...], "linhas": [...], "total_retornado": N}`) ou `(None, mensagem_de_erro)` em caso de erro do Postgres. Reaproveita a lógica de conexão de `tool_consulta_banco`, sem as 5 checagens de texto (isso já é o Validador, Task 2).
  - `responder(ctx: AgentContext, client: OpenAI) -> str` → decide, a partir de `ctx.intencao` e `ctx.tentativas`, se escreve a resposta final a partir de `ctx.resultado_execucao` (dado real), só de `ctx.contexto_rag` (definição), pedindo esclarecimento (`ctx.intencao == "esclarecimento"`), ou explicando falha (tentativas esgotadas) — sempre citando a fonte quando usar `contexto_rag`, sempre em português.

- [ ] **Step 1: Write the failing test (só para `executar_sql`, a parte sem LLM)**

```python
# tests/test_execucao_resposta.py
from scripts.execucao_resposta import executar_sql

def test_executar_sql_sucesso():
    resultado, erro = executar_sql("SELECT COUNT(*) AS total FROM dw.orders")
    assert erro is None
    assert resultado["total_retornado"] == 1
    assert resultado["linhas"][0]["total"] > 0

def test_executar_sql_erro_de_sintaxe_nao_derruba_processo():
    resultado, erro = executar_sql("SELECT coluna_que_nao_existe FROM dw.orders")
    assert resultado is None
    assert erro is not None
```

Este teste precisa do Postgres rodando (`docker compose up -d`) e da role `agente_leitura` já criada — mesmo pré-requisito que os testes da E4 já tinham.

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec app pytest tests/test_execucao_resposta.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'scripts.execucao_resposta'`

- [ ] **Step 3: Implementar `executar_sql` em `scripts/execucao_resposta.py`**

Mesma lógica de conexão/`LIMIT`/tratamento de `psycopg.Error` que `tool_consulta_banco` (Task de referência: `scripts/tools.py:120-150`), sem as checagens de texto (o SQL já passou pelo Validador antes de chegar aqui).

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec app pytest tests/test_execucao_resposta.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Implementar `RESPOSTA_SYSTEM_PROMPT` e `responder` em `scripts/execucao_resposta.py`**

Um prompt curto por ramo (4 instruções de formatação possíveis dependendo de `ctx.intencao`/`ctx.resultado_execucao`/tentativas esgotadas), chamando `client.chat.completions.create` sem `tools`. Trata explicitamente o caso de `resultado_execucao["linhas"] == []` (dizer que não há resultado, nunca inventar número) e o caso de tentativas esgotadas (explicar o que não foi possível responder).

- [ ] **Step 6: Verificação manual com chamada real**

```bash
docker compose exec app python -c "
from openai import OpenAI
import os
from scripts.state import AgentContext
from scripts.execucao_resposta import executar_sql, responder
client = OpenAI(base_url=os.getenv('NVIDIA_BASE_URL', 'https://integrate.api.nvidia.com/v1'), api_key=os.environ['NVIDIA_API_KEY'])
ctx = AgentContext(pergunta='quantos pedidos existem?', intencao='dado')
ctx.resultado_execucao, ctx.erro_execucao = executar_sql('SELECT COUNT(*) AS total FROM dw.orders')
ctx.contexto_rag = [{'fonte': 'Pedido', 'tipo': 'tabela', 'conteudo': 'dw.orders, uma linha por pedido.'}]
print(responder(ctx, client))
"
```
Expected: resposta em português, citando a fonte, com o número real de pedidos (99.441).

- [ ] **Step 7: Commit**

```bash
git add scripts/execucao_resposta.py tests/test_execucao_resposta.py
git commit -m "E5: Agente Execucao e Resposta"
```

---

## Task 8: Prova de que os 3 agentes com LLM funcionam isolados (5.1)

**Files:**
- Create: `scripts/testar_agentes_individuais.py`
- Create: `docs/e5_testes_agentes_individuais.md` (gerado pelo script, não escrito à mão)

**Interfaces:**
- Consumes: `classificar_intencao` (Task 5), `gerar_sql` (Task 6), `responder`/`executar_sql` (Task 7).
- Produces: um relatório Markdown com 2-3 casos por agente (mesmo padrão de `docs/e4_testes_agente.md`), satisfazendo o "testável sozinho" do item 5.1 para os 3 agentes que usam LLM (Validador e Semântico/RAG já ficaram comprovados pelos testes das Tasks 2 e 4).

- [ ] **Step 1: Escrever `scripts/testar_agentes_individuais.py`**

CLI sem argumentos (`docker compose exec app python scripts/testar_agentes_individuais.py`), roda em sequência:
  - 3 perguntas para `classificar_intencao` (uma clara de cada categoria "definicao", "dado", "esclarecimento" — ex. pergunta vaga tipo "me fala dos vendedores").
  - 2 chamadas de `gerar_sql` (uma sem erro anterior, uma com `erro_anterior` preenchido, pra confirmar que o prompt reage ao erro).
  - 2 chamadas de `responder` (uma com resultado real, uma com `resultado_execucao["linhas"] == []`).
  Escreve um Markdown em `docs/e5_testes_agentes_individuais.md` com pergunta/entrada, saída, e uma linha de avaliação manual (✅/❌) por caso — mesmo formato textual do relatório da E4.

- [ ] **Step 2: Rodar e revisar o relatório**

Run: `docker compose exec app python scripts/testar_agentes_individuais.py`
Expected: gera `docs/e5_testes_agentes_individuais.md` com 7 casos; revisar manualmente cada saída (correção de julgamento humano, como em todas as entregas anteriores) e marcar ✅/❌.

- [ ] **Step 3: Commit**

```bash
git add scripts/testar_agentes_individuais.py docs/e5_testes_agentes_individuais.md
git commit -m "E5: prova individual dos 3 agentes com LLM (item 5.1)"
```

---

## Task 9: O grafo (5.2 e 5.3)

**Files:**
- Create: `scripts/grafo.py`

**Interfaces:**
- Consumes: todos os agentes das Tasks 4-7, `rotear_apos_*` (Task 3), `AgentContext` (Task 1).
- Produces: `montar_grafo() -> CompiledGraph` (ou equivalente do LangGraph) e `run_grafo(pergunta: str, verbose: bool = False) -> AgentContext` em `scripts/grafo.py` — função pública que outros scripts (Task 10, CLI) chamam.

- [ ] **Step 1: Implementar os 5 nós do grafo em `scripts/grafo.py`**

Cada nó é uma função `def no_X(ctx: AgentContext) -> AgentContext` que chama o agente correspondente (Tasks 4-7), atualiza os campos certos do `ctx` (`ctx.registrar(...)` a cada passagem, para o `historico`) e devolve o `ctx` atualizado. Pontos de atenção sobre `ctx.tentativas` (lido pelas funções de roteamento da Task 3 logo depois do nó `validador` e logo depois do nó `execucao_resposta`, antes de decidir se volta pro Gerador de SQL):
  - O nó `validador` incrementa `ctx.tentativas` no momento em que marca `ctx.validacao_ok = False` (antes de devolver o `ctx` — é esse valor que `rotear_apos_validador` vai ler).
  - O nó `execucao_resposta`, quando `executar_sql` devolve um erro, incrementa `ctx.tentativas` no momento em que marca `ctx.erro_execucao` (mesmo raciocínio).
  - O nó `gerador_sql`, ao ser chamado de novo depois de uma rejeição/erro, **limpa** `ctx.validacao_ok`, `ctx.motivo_rejeicao` e `ctx.erro_execucao` (voltam a `None`) antes de gerar o novo SQL — sem isso, o roteamento depois do próximo passo pelo Validador ou pela Execução pode ler um estado de uma tentativa anterior.

- [ ] **Step 2: Montar o `StateGraph` com as arestas condicionais das funções da Task 3**

Usar `langgraph.graph.StateGraph(AgentContext)` (ou um `TypedDict` espelhando os mesmos campos, se o LangGraph exigir — confirmar na implementação qual o `State` type aceito pela versão instalada), nó de entrada `orquestrador`, `add_conditional_edges` usando cada `rotear_apos_*` para apontar para os próximos nós (incluindo os retornos para `gerador_sql` e os `END` a partir de `execucao_resposta`).

- [ ] **Step 3: Implementar `run_grafo` e um `main()` CLI**

`run_grafo` invoca o grafo compilado com um `AgentContext(pergunta=pergunta)` inicial e devolve o `AgentContext` final. `main()` segue o mesmo padrão de `scripts/agent.py` (`argparse`, imprime o histórico passo a passo e a resposta final), para rodar como `docker compose exec app python scripts/grafo.py "pergunta"`.

- [ ] **Step 4: Rodar manualmente uma pergunta de caminho feliz**

Run: `docker compose exec app python scripts/grafo.py "qual foi a receita de 2017?"`
Expected: termina em `execucao_resposta`, resposta final citando fonte e com número real (mesmo valor já visto na E4: R$ 5.962.902,01), `historico` mostrando a passagem por `orquestrador → semantico_rag → gerador_sql → validador → execucao_resposta`.

- [ ] **Step 5: Commit**

```bash
git add scripts/grafo.py
git commit -m "E5: grafo LangGraph ligando os 5 agentes, com loop de correcao (itens 5.2 e 5.3)"
```

---

## Task 10: Testes de integração (5.5) e demonstração end-to-end (5.4)

**Files:**
- Create: `scripts/run_e5_tests.py`
- Create: `docs/e5_testes_integracao.jsonl`, `docs/e5_testes_integracao.md`

**Interfaces:**
- Consumes: `run_grafo` (Task 9).
- Produces: bateria de cenários (mesmo padrão de `scripts/run_agent_tests.py` da E4), cobrindo:
  1. Caminho feliz com dado real (pergunta tipo "qual foi a receita de 2017?").
  2. Pergunta só de definição (pula Gerador de SQL e execução).
  3. Pergunta ambígua (cai em `esclarecimento`, termina sem consultar nada).
  4. SQL rejeitado pelo Validador na primeira tentativa, correto na segunda (prova o loop de correção do lado do Validador).
  5. Execução falha (erro do Postgres) na primeira tentativa, corrige na segunda (prova o loop de correção do lado da execução).
  6. Caso de borda: tentativas esgotadas (forçar, ex. pedindo uma métrica inexistente que sempre gera SQL inválido) — confirma que termina graciosamente, sem travar.
  7. Caso de borda: consulta válida mas sem linhas de resultado — confirma que a resposta diz "nenhum resultado", não inventa número.

- [ ] **Step 1: Escrever `scripts/run_e5_tests.py`**

CLI sem argumentos, roda os 7 cenários chamando `run_grafo`, grava cada `AgentContext` (pergunta, histórico, resposta final, tentativas) em `docs/e5_testes_integracao.jsonl`, e monta `docs/e5_testes_integracao.md` com uma tabela de critérios (mesmo formato da tabela da E4 em `docs/entregas/E4/README.md`: contexto relevante, decisão correta, resposta correta, citou fonte, números inventados).

- [ ] **Step 2: Rodar a bateria (em segundo plano, por causa da latência) e revisar**

Run: `docker compose exec app python scripts/run_e5_tests.py`
Expected: gera os dois arquivos; revisar manualmente cada um dos 7 casos e preencher a avaliação ✅/❌ na tabela, igual ao processo da E4. Qualquer bug encontrado (ex. um roteamento que não dispara como esperado) é uma correção a aplicar e reteste — mesmo padrão do bug de SP/RJ da E4.

- [ ] **Step 3: Commit**

```bash
git add scripts/run_e5_tests.py docs/e5_testes_integracao.jsonl docs/e5_testes_integracao.md
git commit -m "E5: testes de integracao do grafo completo, incluindo casos de borda (item 5.5)"
```

---

## Task 11: Documentação da entrega (E5 README)

**Files:**
- Create: `docs/entregas/E5/README.md`
- Modify: `docs/entregas/README.md` (linha da E5: `⏳ Em breve` → `✅ Concluída`, com link)
- Modify: `README.md` (raiz, tabela de entregas e, se fizer sentido, a seção "Como rodar o projeto" com o novo comando `scripts/grafo.py`)

**Interfaces:**
- Consumes: os relatórios gerados nas Tasks 8 e 10, e o `docs/entregas/E5/design.md` já existente.

- [ ] **Step 1: Escrever `docs/entregas/E5/README.md`**

Mesmo formato de `docs/entregas/E4/README.md`: um título por item (5.1 a 5.5), linkando os scripts e relatórios das tasks anteriores, uma seção final "o que este sistema ainda não é" (sem API/UI — isso é a E6) e as limitações conhecidas (latência, igual às entregas anteriores).

- [ ] **Step 2: Atualizar `docs/entregas/README.md` e `README.md` (raiz)**

Mesmo padrão das atualizações feitas ao concluir a E4.

- [ ] **Step 3: Commit**

```bash
git add docs/entregas/E5/README.md docs/entregas/README.md README.md
git commit -m "E5: documentacao da entrega"
```
