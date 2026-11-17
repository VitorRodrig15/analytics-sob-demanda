# E5 — Sistema Multi-Agente Orquestrado

**Período:** 17/11 a 21/11/2026 · **Foco:** Orquestração · **Status:** ✅ Concluída

Entregáveis 5.1 a 5.5: os 5 agentes especializados da arquitetura da E1 materializados
como módulos separados, um grafo LangGraph de verdade coordenando o fluxo entre eles,
um Validador determinístico (`sqlglot`, sem LLM), um loop de correção formal, uma
demonstração ponta a ponta e uma bateria de testes de integração do grafo completo.

A virada desta entrega, em relação à E4: lá, **um agente só** misturava, num único
prompt, o papel do Agente Semântico/RAG e do Agente de Execução, decidindo tudo via
tool calling solto. Aqui, os 5 agentes desenhados na E1 (Orquestrador, Semântico/RAG,
Gerador de SQL, Validador, Execução e Resposta) existem como peças separadas e
testáveis isoladamente, com um estado compartilhado (`AgentContext`) passando de nó em
nó dentro de um `StateGraph` real, e um Validador que analisa o SQL de forma
determinística — não só confiando no prompt, porque a E4 já mostrou que o modelo nem
sempre segue 100% as regras escritas.

Design completo (intenção, goals, non-goals, decisões fechadas antes de implementar):
[`docs/entregas/E5/design.md`](design.md).

## 5.1 Demais agentes implementados

| Agente | Script | Responsabilidade |
|---|---|---|
| Orquestrador | [`scripts/orquestrador.py`](../../../scripts/orquestrador.py) | Classifica a pergunta em `definicao` / `dado` / `ambas` / `esclarecimento` (uma chamada de LLM dedicada, não heurística por palavra-chave) |
| Semântico/RAG | [`scripts/semantico_rag.py`](../../../scripts/semantico_rag.py) | Busca no dicionário semântico (schema `rag`) o contexto relevante para a pergunta, reaproveitando `retrieve()` da E3 |
| Gerador de SQL | [`scripts/gerador_sql.py`](../../../scripts/gerador_sql.py) | Escreve o SQL a partir do contexto do RAG, reagindo a um `erro_anterior` (de validação ou de execução) quando existe |
| Validador | [`scripts/validador.py`](../../../scripts/validador.py) | Análise estática determinística do SQL via `sqlglot` (árvore real, não regex): só `SELECT`, só tabelas `dw.*`, sem sub-statements perigosos |
| Execução e Resposta | [`scripts/execucao_resposta.py`](../../../scripts/execucao_resposta.py) | Roda o SQL aprovado (role `agente_leitura`, a mesma da E4) e escreve a resposta final em português, citando a fonte |

**Prova de que cada um funciona isolado:** script
[`scripts/testar_agentes_individuais.py`](../../../scripts/testar_agentes_individuais.py),
relatório em [`docs/e5_testes_agentes_individuais.md`](../../e5_testes_agentes_individuais.md).
7 chamadas reais de LLM contra os 3 agentes que só são testáveis com LLM (Orquestrador,
Gerador de SQL, Execução e Resposta) — Validador e Semântico/RAG já tinham prova própria
nas Tasks 2 e 4. Resultado final: **7/7 ✅**, depois de um round de correção: o caso G2
(reação a `erro_anterior`) inicialmente usava um erro sintético que a query nem
referenciava e não provava reação nenhuma; regerado com um erro amarrado ao filtro de
data real usado pela query, o novo SQL reagiu de forma visível
(`EXTRACT(YEAR FROM ...) = 2017`).

**Achado que vale registrar:** durante a construção do Validador foi encontrado e
corrigido um bypass de segurança real — a exclusão de nomes de CTE usava
`find_all(exp.CTE)` sobre a árvore inteira em vez de ficar escopada ao `WITH` que de
fato envolve a tabela sendo checada, então um CTE dentro de uma subquery não
relacionada, com o mesmo nome de uma tabela de verdade fora do schema `dw`, enganava a
checagem e passava `ok=True` — reproduzido com 2 SQLs de ataque antes da correção.
Corrigido escopando a busca de nomes de CTE só ao `WITH` de topo, com teste de
regressão cobrindo o caso de ataque.

## 5.2 Orquestração implementada

**Script:** [`scripts/grafo.py`](../../../scripts/grafo.py) — monta um `StateGraph`
(LangGraph) ligando os 5 agentes, com arestas condicionais decidindo o próximo nó a
partir do estado (`scripts/grafo_routing.py` concentra as 4 funções `rotear_apos_*`).
Toda rota termina em `execucao_resposta`, seja com dado real, só definição do RAG, um
pedido de esclarecimento, ou uma explicação de falha.

**Loop de correção:** um único contador de tentativas (`ctx.tentativas`), compartilhado
entre os dois motivos de retorno ao Gerador de SQL — reprovação do Validador e erro de
execução do Postgres — até um limite (`MAX_TENTATIVAS = 3`). Ao esgotar, o grafo roteia
direto para `execucao_resposta` em modo "não consegui responder", em vez de tentar para
sempre.

**Bug real achado e corrigido durante a construção (dry-run, antes do commit):** a
aresta condicional de saída de `execucao_resposta` decidia END-vs-retentativa checando
`ctx.erro_execucao`, que nunca era limpo no self-loop "esgotado" — isso causava um
`GraphRecursionError` (loop infinito). Corrigido checando `ctx.resposta_final` (só
setado depois que `responder()` de fato roda), mesmo princípio do `MAX_RODADAS` da E4
que evita um loop sem fim.

## 5.3 Gestão de estado

**Script:** [`scripts/state.py`](../../../scripts/state.py) — dataclass `AgentContext`
com a pergunta, a intenção classificada, o contexto do RAG, o SQL gerado, o resultado da
validação (`validacao_ok`/`motivo_rejeicao`), o resultado da execução
(`resultado_execucao`/`erro_execucao`), a resposta final, o contador de tentativas e o
`historico` (log passo a passo de cada nó percorrido).

Cada nó do grafo lê só os campos de que precisa, roda sua tarefa e devolve só os campos
que mudou — o `StateGraph` do LangGraph (confirmado rodando, não assumido: a versão
1.2.19 aceita o dataclass direto como schema) cuida de mesclar no estado global.
`ctx.registrar()` é quem popula o `historico`, usado tanto na demonstração do 5.4
quanto para os testes do 5.5 inspecionarem o caminho percorrido sem reconstruir logs
externos. Um detalhe confirmado na revisão: no caminho de tentativas esgotadas por erro
de execução, `execucao_resposta` aparece 2x no `historico` (uma pela tentativa que
falhou, outra pela resposta final) — comportamento esperado, não uma duplicação
indevida.

## 5.4 Fluxo end-to-end do sistema

Rodada manual real: `docker compose exec app python scripts/grafo.py "qual foi a
receita de 2017?"`.

**Caminho percorrido (via `historico`):** orquestrador (classificou `dado`) →
semântico_rag (trouxe 3 trechos do dicionário, incluindo "Receita") → gerador_sql →
validador (aprovado de primeira) → execucao_resposta (executou o SQL e narrou o
resultado).

**Resposta final:** **R$ 5.962.902,01**, com a fonte citada — mesmo valor reconfirmado
depois, de forma independente, no cenário 1 da bateria de integração do 5.5.

## 5.5 Testes de integração

**Script:** [`scripts/run_e5_tests.py`](../../../scripts/run_e5_tests.py). Relatório:
[`docs/e5_testes_integracao.md`](../../e5_testes_integracao.md). Resultados brutos (um
`AgentContext` completo por linha, incluindo o `historico`):
[`docs/e5_testes_integracao.jsonl`](../../e5_testes_integracao.jsonl).

Bateria de 7 cenários cobrindo toda a matriz de comportamento do grafo: caminho feliz
com dado real, definição pura, pergunta ambígua (esclarecimento), Validador rejeita e
corrige, execução falha e corrige, tentativas esgotadas, e consulta válida sem
resultado. Nenhuma chamada de LLM foi mockada.

**Resultado honesto (não "7/7 perfeito"):**
- **4 dos 7** cenários reproduziram exatamente como planejado: caminho feliz
  (R$ 5.962.902,01, igual ao 5.4), definição pura, esclarecimento, e consulta sem
  resultado (via um retry, ver abaixo).
- **Cenários #4 e #6 trocaram de papel na prática:** a pergunta desenhada para
  "Validador rejeita uma vez e corrige na segunda" (#4) na verdade esgotou as 3
  tentativas sem nunca produzir SQL válido; a desenhada para "tentativas esgotadas"
  (#6) foi rejeitada só uma vez e corrigida na segunda. Os dois comportamentos-alvo
  foram observados de verdade, só não nas perguntas planejadas para cada um.
- **Cenário #5 (execução falha e corrige) ficou só parcialmente provado:** a pergunta
  original nunca chegou a falhar na execução (o Validador rejeitou antes, por erro de
  sintaxe, e a correção seguinte já passou e executou com sucesso). Um retry (`5b`,
  pedindo CNPJ/telefone de vendedor — campos que não existem no schema) disparou um
  erro real de execução do Postgres (`column s.seller_cnpj does not exist`) na 3ª
  tentativa, provando que a aresta de correção por erro de execução dispara de
  verdade — mas essa já era a última tentativa do orçamento, então o grafo esgotou em
  vez de corrigir com sucesso. Fica confirmado que o loop de execução dispara com um
  erro real; não fica confirmado que ele corrige a tempo dentro de 3 tentativas.
- **Cenário #7 precisou de um retry para exercer o código certo:** a pergunta original
  devolveu 1 linha com valor `NULL` agregado (não lista vazia), então o ramo dedicado
  "sem resultado" de `execucao_resposta.py` (`if not linhas`) nunca disparou — a
  resposta correta veio do julgamento da própria LLM ao ver `None`, não do código
  determinístico. Um retry (`7b`, filtro logicamente impossível) confirmou o ramo
  dedicado de linhas vazias de verdade.

Nenhum dos dois achados acima (#5 e #7) foi maquiado para parecer "passou" — estão
documentados como lacunas de cobertura reais em
[`docs/e5_testes_integracao.md`](../../e5_testes_integracao.md), que é o relatório
completo com o histórico passo a passo de cada cenário.

## O que este sistema ainda não é

- **Não tem API HTTP nem interface de usuário** — o grafo só é chamado por linha de
  comando (`scripts/grafo.py`); expor isso como serviço é a E6.
- **Não tem dataset/métricas de avaliação formal** — os testes aqui são uma bateria
  pequena e curada (mesmo padrão de E1 a E4), não uma avaliação sistemática; isso é a
  E7.
- **Não tem esclarecimento multi-turno de verdade** — o fluxo de "esclarecimento" pede
  o esclarecimento em texto e termina a execução ali, sem o usuário poder responder e o
  grafo continuar de onde parou. Isso é decisão explícita de escopo (ver
  "Decisões adicionais" em `design.md`): multi-turno real depende de API/UI, que é a
  E6.

## Limitação conhecida

A latência do GPT-OSS-20B (~130-180s por chamada, documentada desde a E3) continua
sendo a limitação principal — e aqui ela se multiplica: o caminho feliz completo
(Orquestrador → Semântico/RAG → Gerador de SQL → Validador → Execução e Resposta) já
soma **3 chamadas de LLM**, e cada volta do loop de correção soma mais uma. Isso é
esperado desde o design (constraint já aceita) e segue sendo mitigado com testes em
segundo plano e respostas pré-computadas para qualquer demonstração ao vivo.
