# E4 — Primeiro Agente Funcional

**Período:** 10/11 a 14/11/2026 · **Foco:** Agente · **Status:** ✅ Concluída

Entregáveis 4.1 a 4.5: primeiro agente com tool calling de verdade, integração com o
RAG como ferramenta, definição das tools, testes do agente isolado e esta documentação.

A virada desta entrega, em relação à E3: no `rag_pipeline.py` (3.3), **o código**
decidia o caminho (sempre busca → sempre monta prompt → sempre chama a LLM, igual pra
toda pergunta). Aqui, **a LLM decide**, a cada pergunta, se busca no dicionário, se
consulta o banco, as duas coisas, nenhuma, ou se pede esclarecimento — usando tool
calling real (o parâmetro `tools` da API, formato OpenAI).

## 4.1 Primeiro agente implementado

**Script:** [`scripts/agent.py`](../../../scripts/agent.py) — função `run_agent(pergunta)`.

**Papel do agente:** assistente de analytics da Vortex Marketplace, que responde
perguntas de negócio em linguagem natural usando o dicionário semântico e os dados
reais do schema `dw`, sem o gestor precisar escrever SQL.

**Responsabilidades:**
- Decidir, a cada pergunta, se precisa buscar uma definição/fórmula, consultar o banco,
  ambos, ou se deve recusar/pedir esclarecimento.
- Nunca inventar números, fórmulas ou nomes de tabela.
- Citar a fonte de toda definição usada.
- Recusar qualquer tentativa de alterar dados.

**Entrada:** uma pergunta em português, em texto livre.
**Saída estruturada:** um `AgentResult` (dataclass) com a pergunta, a lista de chamadas
de ferramenta feitas (nome, argumentos, resultado), a resposta final em texto e o
número de rodadas até concluir.

**Como funciona o loop de decisão:** a cada rodada, a LLM recebe o histórico da
conversa e a lista de ferramentas disponíveis. Se ela pedir uma ferramenta, o código
executa de verdade e devolve o resultado; se ela responder só com texto (sem pedir
ferramenta), é a resposta final. Uma trava (`MAX_RODADAS = 5`) evita loop infinito.

## 4.2 Integração do agente com o RAG

A busca vetorial da E3 (`retrieve()`, em `search.py`) virou a ferramenta
`busca_vetorial` — uma entre duas que o agente tem disponíveis, e é **a própria LLM**
quem decide se e quando chamá-la, não mais um fluxo fixo em Python. Na prática, em
6 dos 7 testes do 4.4 o agente chamou `busca_vetorial` antes de qualquer outra coisa,
seguindo a regra 1 do prompt ("nunca escreva uma fórmula de memória").

## 4.3 Definição de tools/functions

**Script:** [`scripts/tools.py`](../../../scripts/tools.py).

| Ferramenta | O que faz | Protege contra |
|---|---|---|
| `busca_vetorial` | Busca no schema `rag` (dicionário semântico) os chunks mais parecidos com a pergunta | Retentativa automática para erros transitórios da API de embedding |
| `consulta_banco` | Executa um `SELECT` real no schema `dw`, usando a role `agente_leitura` | 5 verificações antes de rodar (só SELECT, 1 instrução, sem palavras de escrita, tabela do `dw` obrigatória, tamanho máximo) + o próprio PostgreSQL recusa qualquer escrita, porque a role nasce em modo somente leitura |

Decidi **não** criar uma terceira tool "formata_resposta": a resposta final é só o
texto comum que a LLM escreve quando já tem o que precisa — não existe código a
executar ali.

**Segurança (pré-requisito desta entrega):** antes de escrever `consulta_banco`, criei
a role `agente_leitura` ([`sql/agent_readonly_role.sql`](../../../sql/agent_readonly_role.sql)),
testada na prática: ela consulta `dw.orders` normalmente, mas um `INSERT` de teste foi
recusado pelo próprio banco, sem nenhuma lógica de aplicação no meio.

## 4.4 Testes do agente isolado

Bateria de 7 cenários, cobrindo toda a matriz de decisão possível. Relatório completo
em [`docs/e4_testes_agente.md`](../../e4_testes_agente.md), respostas brutas em
[`docs/e4_testes_agente.jsonl`](../../e4_testes_agente.jsonl).

| Critério | Resultado |
|---|---|
| Contexto relevante | 6/7 |
| Decisão correta (ferramenta certa) | 6/7 → 7/7 após correção |
| Resposta correta/completa | 6/7 → 7/7 após correção |
| Citou a fonte | 6/6 (100% do que era aplicável) |
| Números inventados | 0/7 |

**O único problema encontrado:** numa pergunta de comparação geográfica, o agente
buscou pela tabela errada (`dw.orders`, que não tem cidade) e não respondeu nada.
Corrigido no mesmo dia com uma regra explícita no prompt apontando que localização
fica em `dw.customers`/`dw.sellers` — testado de novo e confirmado funcionando, com
números reais e JOIN correto.

**Dois bugs de integração encontrados e corrigidos durante a construção** (antes da
bateria formal), que valem registrar:
1. Um erro transitório da API de embedding derrubava o processo inteiro — ferramentas
   agora sempre devolvem um erro tratado, nunca travam o loop.
2. O GPT-OSS às vezes cola um artefato do seu formato interno no nome da função
   chamada (`consulta_banco<|channel|>commentary`) — corrigido removendo esse sufixo
   antes de despachar a ferramenta.

## 4.5 Documentação do agente

Esta página. Resumo dos critérios de decisão que o agente segue (as 8 regras do
`AGENT_SYSTEM_PROMPT`, em `scripts/agent.py`):

1. Sempre buscar a fórmula/regra no dicionário antes de escrever SQL.
2. Só consultar o banco quando a pergunta pedir um número, comparação ou lista real.
3. Nunca tentar calcular uma métrica que o dicionário marca como indisponível.
4. Se o SQL der erro, tentar corrigir uma vez; se persistir, explicar o que não foi
   possível responder.
5. Sempre citar a fonte da definição usada.
6. Nunca tentar um comando de escrita.
7. Responder em português, direto, sem expor SQL cru sem necessidade.
8. Região/cidade/estado do cliente estão em `dw.customers`, do vendedor em
   `dw.sellers` — nunca em `dw.orders` (regra acrescentada após o 4.4).

**O que este agente ainda não é:** ele é **um** agente isolado, prototipando ao mesmo
tempo um pouco do papel do Agente Semântico/RAG e do Agente de Execução, desenhados na
E1. A separação em 5 agentes especializados, orquestrados por um Agente Orquestrador
com loop de correção formal e um Agente Validador dedicado, é o trabalho da E5.

**Limitação conhecida, documentada e aceita nesta etapa:** a latência do GPT-OSS-20B
(~130-180s por chamada, ver E3) significa que uma pergunta com 2-4 rodadas de decisão
pode levar vários minutos. Isso já era esperado desde a E3 e segue sendo mitigado com
testes em segundo plano e respostas pré-computadas para qualquer demonstração ao vivo.
