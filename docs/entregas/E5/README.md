# E5 — Sistema Multi-Agente Orquestrado

**Período:** 17/11 a 21/11/2026 · **Foco:** Orquestração · **Status:** ✅ Concluída

Esta entrega cobre os itens 5.1 a 5.5: peguei os 5 agentes especializados que desenhei
lá na E1 e finalmente os construí separados de verdade, liguei todos num grafo
LangGraph de verdade, escrevi um Validador que analisa o SQL sem depender de LLM
nenhuma, montei o loop de correção formal entre eles, e documentei tudo com uma
demonstração ponta a ponta e uma bateria de testes de integração.

A diferença em relação à E4 é essa: lá eu tinha **um agente só**, que misturava num
único prompt o papel do Agente Semântico/RAG e do Agente de Execução, decidindo tudo
via tool calling solto. Funcionava, mas não era a arquitetura que eu tinha desenhado na
E1. Agora os 5 agentes (Orquestrador, Semântico/RAG, Gerador de SQL, Validador,
Execução e Resposta) são módulos separados, cada um testável sozinho, com um estado
compartilhado (`AgentContext`) passando de nó em nó dentro de um `StateGraph` de
verdade. E o Validador analisa o SQL de forma determinística, sem confiar só no
prompt — a E4 já tinha me mostrado que o modelo nem sempre segue 100% as regras
escritas, então aqui ele não é a única linha de defesa.

O design completo, com a intenção, os goals/non-goals e as decisões que fechei antes
de começar a codar, está em [`docs/entregas/E5/design.md`](design.md).

## Apresentação desta entrega

- [Ver o código-fonte no GitHub](../../apresentacoes/apresentacao_E5/apresentacao_E5.html)
- [Baixar só a apresentação (.zip)](../../apresentacoes/apresentacao_E5.zip) — baixa e extraia para abrir o `.html` localmente, sem clonar o repositório inteiro

## 5.1 Demais agentes implementados

| Agente | Script | Responsabilidade |
|---|---|---|
| Orquestrador | [`scripts/orquestrador.py`](../../../scripts/orquestrador.py) | Classifica a pergunta em `definicao` / `dado` / `ambas` / `esclarecimento` (uma chamada de LLM dedicada, não heurística por palavra-chave) |
| Semântico/RAG | [`scripts/semantico_rag.py`](../../../scripts/semantico_rag.py) | Busca no dicionário semântico (schema `rag`) o contexto relevante para a pergunta, reaproveitando o `retrieve()` que já tinha da E3 |
| Gerador de SQL | [`scripts/gerador_sql.py`](../../../scripts/gerador_sql.py) | Escreve o SQL a partir do contexto do RAG, e reage quando existe um erro da tentativa anterior (de validação ou de execução) |
| Validador | [`scripts/validador.py`](../../../scripts/validador.py) | Análise estática determinística via `sqlglot` — a árvore real do SQL, não regex. Só aceita `SELECT`/`WITH`/`UNION`/`EXCEPT`/`INTERSECT`, exige pelo menos uma tabela `dw.*` referenciada, e rejeita qualquer `INSERT`/`UPDATE`/`DELETE`/`MERGE`/`CREATE`/`DROP` em qualquer nível da árvore — mesmo escondido dentro de uma CTE — e qualquer `SELECT ... INTO` |
| Execução e Resposta | [`scripts/execucao_resposta.py`](../../../scripts/execucao_resposta.py) | Roda o SQL aprovado (role `agente_leitura`, a mesma da E4) e escreve a resposta final em português, citando a fonte |

Pra provar que cada agente funciona isolado, sem depender do grafo, escrevi o
[`scripts/testar_agentes_individuais.py`](../../../scripts/testar_agentes_individuais.py)
— 7 chamadas reais de LLM contra os 3 agentes que só dá pra testar com LLM de verdade
(Orquestrador, Gerador de SQL, Execução e Resposta; o Validador e o Semântico/RAG já
tinham prova própria das Tasks 2 e 4). O relatório completo está em
[`docs/e5_testes_agentes_individuais.md`](../../e5_testes_agentes_individuais.md).
Fechou em **7/7 ✅**, mas só depois de uma correção: o primeiro caso que testava a
reação do Gerador de SQL a um erro anterior usava um erro sintético que a query nem
sequer referenciava, então não provava nada de verdade. Regerei com um erro amarrado
ao filtro de data que a query realmente usa, e aí o SQL reagiu de forma visível
(`EXTRACT(YEAR FROM ...) = 2017`).

Vale registrar dois achados de segurança no caminho. O primeiro apareceu ainda durante
a construção do Validador: a lógica que excluía nomes de CTE usava `find_all(exp.CTE)`
na árvore inteira, em vez de ficar restrita ao `WITH` que de fato envolvia a tabela
sendo checada. Na prática, isso significava que um CTE dentro de uma subquery sem
relação nenhuma, com o mesmo nome de uma tabela de verdade fora do schema `dw`,
enganava a checagem e passava como válido — reproduzi com dois SQLs de ataque antes de
corrigir. A correção foi escopar a busca de nomes de CTE só ao `WITH` de topo, com um
teste de regressão cobrindo o ataque.

O segundo bypass só apareceu na revisão final do branch inteiro, depois que tudo já
parecia pronto. A regra "só `SELECT`" checava apenas se o statement de topo (ou o
`SELECT` interno de um `WITH`) era um `exp.Select`, sem olhar a árvore por inteiro —
o que deixava passar um `INSERT`/`UPDATE`/`DELETE` escondido dentro de uma CTE com
`RETURNING` (por exemplo, `WITH x AS (DELETE FROM dw.orders RETURNING *) SELECT * FROM
x`) e também um `SELECT ... INTO`, que cria uma tabela nova. Corrigi com uma busca por
qualquer `exp.Insert`/`exp.Update`/`exp.Delete`/`exp.Merge`/`exp.Create`/`exp.Drop` em
qualquer nível da árvore, mais uma checagem dedicada pro `args["into"]`, com testes de
regressão pros dois ataques. Aproveitei a mesma revisão pra endurecer a regra do schema
`dw`: antes bastava não ter nenhuma tabela fora dele, o que deixava passar uma consulta
sem nenhuma tabela real (tipo `SELECT 'texto' AS msg`); agora exijo pelo menos uma
tabela `dw.*` de verdade.

## 5.2 Orquestração implementada

O [`scripts/grafo.py`](../../../scripts/grafo.py) monta um `StateGraph` do LangGraph
ligando os 5 agentes, com arestas condicionais decidindo o próximo nó a partir do
estado — as 4 funções `rotear_apos_*` que concentrei em
`scripts/grafo_routing.py`. Toda rota termina em `execucao_resposta`, seja com dado
real, só com a definição do RAG, um pedido de esclarecimento, ou uma explicação de
falha.

O loop de correção usa um único contador de tentativas (`ctx.tentativas`),
compartilhado entre os dois motivos que mandam de volta pro Gerador de SQL: uma
reprovação do Validador ou um erro de execução do Postgres. Até um limite de 3
tentativas (`MAX_TENTATIVAS`). Quando esgota, o grafo roteia direto pra
`execucao_resposta` em modo "não consegui responder", em vez de tentar pra sempre.

Achei um bug real ainda durante a construção, antes de commitar: a aresta condicional
de saída de `execucao_resposta` decidia entre terminar ou tentar de novo checando
`ctx.erro_execucao` — só que esse campo nunca era limpo no self-loop do caso
"esgotado", e isso causava um `GraphRecursionError`, um loop infinito de verdade.
Corrigi checando `ctx.resposta_final` em vez disso, que só fica preenchido depois que
`responder()` realmente roda — o mesmo princípio do `MAX_RODADAS` que já usava na E4
pra evitar um loop sem fim.

## 5.3 Gestão de estado

O [`scripts/state.py`](../../../scripts/state.py) define o `AgentContext`, a dataclass
que carrega a pergunta, a intenção já classificada, o contexto do RAG, o SQL gerado, o
resultado da validação (`validacao_ok`/`motivo_rejeicao`), o resultado da execução
(`resultado_execucao`/`erro_execucao`), a resposta final, o contador de tentativas e o
`historico` — um log passo a passo de cada nó por onde a pergunta passou.

Cada nó do grafo lê só os campos que precisa, faz sua parte, e devolve só o que mudou;
quem cuida de mesclar isso de volta no estado global é o próprio `StateGraph` do
LangGraph (e confirmei rodando, não assumi — a versão 1.2.19 aceita o dataclass direto
como schema, sem precisar converter pra `TypedDict`). O `ctx.registrar()` é quem
popula o `historico`, e é esse histórico que uso tanto na demonstração do 5.4 quanto
nos testes do 5.5 pra inspecionar o caminho percorrido sem precisar reconstruir logs
externos. Um detalhe que só confirmei na revisão: no caminho em que as tentativas se
esgotam por erro de execução, `execucao_resposta` aparece duas vezes no `historico` —
uma pela tentativa que falhou, outra pela resposta final. É esperado, não uma
duplicação indevida.

## 5.4 Fluxo end-to-end do sistema

Rodei de verdade: `docker compose exec app python scripts/grafo.py "qual foi a receita
de 2017?"`.

Pelo `historico`, o caminho foi: orquestrador classificou como `dado` → semântico_rag
trouxe 3 trechos do dicionário, incluindo o de "Receita" → gerador_sql escreveu a
consulta → validador aprovou de primeira → execucao_resposta rodou o SQL e narrou o
resultado.

A resposta final veio **R$ 5.962.902,01**, com a fonte citada — o mesmo valor que
reconfirmei depois, de forma independente, no primeiro cenário da bateria de
integração do 5.5.

## 5.5 Testes de integração

Escrevi o [`scripts/run_e5_tests.py`](../../../scripts/run_e5_tests.py) pra rodar 7
cenários reais contra o grafo completo, sem mockar nenhuma chamada de LLM. O relatório
está em [`docs/e5_testes_integracao.md`](../../e5_testes_integracao.md), e os
resultados brutos — um `AgentContext` completo por linha, incluindo o `historico` — em
[`docs/e5_testes_integracao.jsonl`](../../e5_testes_integracao.jsonl).

Os 7 cenários cobrem toda a matriz de comportamento do grafo: caminho feliz com dado
real, definição pura, pergunta ambígua (esclarecimento), Validador rejeitando e
corrigindo, execução falhando e corrigindo, tentativas esgotadas, e uma consulta válida
sem resultado nenhum.

E aqui prefiro ser direto: não foi "7/7 perfeito". Quatro dos sete cenários
reproduziram exatamente como eu tinha planejado — caminho feliz (de novo R$
5.962.902,01, batendo com o 5.4), definição pura, esclarecimento, e a consulta sem
resultado (essa precisou de um retry, explico abaixo). Os outros três tiveram
surpresas, porque a LLM não é determinística e as perguntas foram desenhadas pra
*induzir* um caminho, não pra garantir:

- Os cenários #4 e #6 trocaram de papel na prática. A pergunta que eu tinha desenhado
  pra mostrar "o Validador rejeita uma vez e corrige na segunda" (#4) na verdade
  esgotou as 3 tentativas sem nunca produzir um SQL válido; e a que eu tinha desenhado
  pra mostrar "tentativas esgotadas" (#6) foi rejeitada só uma vez e corrigiu na
  segunda. Os dois comportamentos aconteceram de verdade — só não nas perguntas que eu
  esperava.
- O cenário #5, que devia provar "a execução falha e corrige", ficou só parcialmente
  provado. A pergunta original nunca chegou a falhar na execução — o Validador rejeitou
  antes, por um erro de sintaxe, e a correção seguinte já passou direto. Fiz um retry
  (pedindo CNPJ e telefone de vendedor, campos que não existem no schema) e aí sim
  disparou um erro real do Postgres na terceira tentativa — mas essa já era a última do
  orçamento, então o grafo esgotou em vez de corrigir a tempo. Fica confirmado que o
  loop de correção por erro de execução dispara de verdade; não fica confirmado que ele
  consegue corrigir dentro de 3 tentativas.
- O cenário #7 precisou de um retry pra exercer o código certo. A pergunta original
  devolveu uma linha com valor `NULL` agregado, não uma lista vazia — então o ramo
  dedicado pra "sem resultado" em `execucao_resposta.py` nunca chegou a disparar, e a
  resposta correta saiu do próprio julgamento da LLM ao ver o `None`, não do código
  determinístico. Um segundo retry, com um filtro logicamente impossível, confirmou o
  ramo dedicado de verdade.

Nenhum desses dois achados (#5 e #7) foi maquiado pra parecer que passou — estão
documentados como lacunas de cobertura reais no relatório completo.

E tem mais uma correção que só apareceu na revisão final do branch inteiro: todas as
rejeições do Validador registradas na bateria (contadas nos históricos como "0
instruções SQL") foram causadas por saída vazia ou truncada do `gerador_sql.py`, por
causa do limite de tokens (`MAX_TOKENS = 700`, insuficiente pras perguntas mais
complexas) — nenhuma delas foi o Validador rejeitando uma violação real de schema ou
tipo de statement. Já corrigi isso (`MAX_TOKENS` subiu pra 1500), mas não re-executei a
bateria inteira depois — o custo de latência não compensava. Os números acima
continuam os mesmos; só a causa raiz das rejeições ficou corretamente atribuída.

## O que este sistema ainda não é

Ainda não tem API nem interface de usuário — o grafo só é chamado por linha de
comando. Expor isso como serviço é trabalho da E6.

Também não tem um dataset ou métricas de avaliação formal; os testes aqui são uma
bateria pequena e curada, do mesmo jeito que fiz de E1 a E4, não uma avaliação
sistemática. Isso fica pra E7.

E não tem um esclarecimento multi-turno de verdade: quando o fluxo cai em
"esclarecimento", ele pede o esclarecimento em texto e termina ali, sem o usuário
poder responder e o grafo continuar de onde parou. Isso foi decisão explícita de
escopo (está nas "Decisões adicionais" do `design.md`) — multi-turno real depende de
API/UI, que também é trabalho da E6.

## Adendo (18/11/2026): o GPT-OSS-20B saiu do ar no meio da entrega

No dia em que fui gravar a demonstração pra apresentar esta entrega, um colega me
avisou que o modelo tinha sido desligado. Confirmei direto contra a API da NVIDIA: o
`openai/gpt-oss-20b` — o modelo que todo o resto deste documento cita, e que gerou
todos os números e exemplos acima — teve fim de vida às 08h UTC do próprio dia
18/11/2026 (`Error code: 410`, `"has reached its end of life"`). Isso não é um erro
de configuração nem algo que eu tivesse como prever: a NVIDIA descontinuou o modelo
do lado deles, sem aviso prévio no meu fluxo de trabalho.

Na prática, isso derrubava toda chamada de LLM do sistema — Orquestrador, Gerador de
SQL, Execução e Resposta — mesmo com o código 100% correto. O Validador (determinístico,
sem LLM) e a suíte `pytest` continuaram funcionando normalmente o tempo todo, já que não
dependem de nenhuma chamada externa.

**O que fiz:** consultei o catálogo de modelos disponíveis direto pela API (não por
documentação, que podia estar desatualizada) e testei dois candidatos da família
Nemotron da própria NVIDIA com prompts reais — incluindo um de geração de SQL, igual ao
que o Gerador de SQL faz de verdade. Escolhi o `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`:
respondeu corretamente nos testes, e separa o raciocínio interno (`reasoning_content`) do
texto final (`content`) em campos diferentes da resposta — o mesmo tipo de canal de
raciocínio que o GPT-OSS-20B já tinha, só que exposto de forma mais limpa.

Troquei o `LLM_MODEL` padrão em todos os scripts que chamam a LLM (Orquestrador, Gerador
de SQL, Execução e Resposta, mais os scripts de teste e os reaproveitados da E3/E4), no
`.env` local e no `.env.example` versionado, reconstruí a imagem Docker (uma dependência,
`sqlglot`, só estava instalada na imagem antiga de forma avulsa) e rodei de novo a suíte
inteira: **32/32 testes automatizados passando**, a bateria dos 3 agentes com LLM
(5.1) **7/7** de novo, e o fluxo end-to-end do 5.4 confirmado com o mesmo valor de antes
(R$ 5.962.902,01).

O ganho mais visível foi a latência: o que levava de 130 a 180 segundos por chamada
agora leva de 1 a 8 segundos. Uma pergunta que antes demorava 6 a 9 minutos pra
responder (3 chamadas de LLM) agora responde em 15 a 20 segundos. A bateria dos 7
agentes individuais, que antes levava 15 a 25 minutos, rodou em 47 segundos.

**Um achado real durante a re-verificação:** numa pergunta bem mais complexa (comparar
receita por vendedor, por região, por trimestre, mais frete médio — vários agrupamentos
ao mesmo tempo), o modelo novo gastou mais de 2200 tokens só "pensando" antes de montar
o SQL, e o orçamento que eu tinha herdado do GPT-OSS-20B (`MAX_TOKENS = 1500` no Gerador
de SQL) não foi suficiente, truncando a resposta e derrubando as 3 tentativas do loop de
correção. Confirmei isolando a chamada e testando 1500/2500/4000 tokens de orçamento
diretamente contra a API antes de mudar qualquer coisa, e subi o limite para `4000`.

**Uma observação sem solução de código, só de infraestrutura:** o modelo de embeddings
usado pelo RAG (`nvidia/nemotron-3.5-embed-1b`, inalterado por esta migração) "dorme"
depois de um tempo sem uso no tier gratuito da NVIDIA, e a primeira chamada depois disso
estoura o timeout de 60 segundos. Antes, isso passava quase despercebido porque as
chamadas de LLM já eram lentas por padrão; agora que o resto ficou rápido, esse
"despertar" do modelo de embeddings é, proporcionalmente, o maior ponto de instabilidade
de latência do sistema. Pra qualquer demonstração ao vivo, vale fazer uma chamada de
aquecimento antes.

Por honestidade, registro também que, ao tentar re-rodar a bateria completa de
integração (5.5) com os dois ajustes acima já aplicados, enfrentei instabilidade real da
API da NVIDIA (timeouts repetidos, inclusive após reiniciar o container) — muito
provavelmente por causa do volume alto de chamadas que eu mesmo fiz nesta janela curta,
testando e comparando modelos. Não consegui fechar uma segunda rodada completa e limpa
do 5.5 antes de fechar este adendo. O que tenho de verificação sólida: a suíte
determinística (32/32), a bateria 5.1 (7/7, re-executada do zero com o modelo novo) e o
fluxo 5.4 (confirmado duas vezes) — mais a correção pontual do achado acima, testada
isoladamente e de forma repetível. Recomendo rodar o `scripts/run_e5_tests.py` mais uma
vez, com calma, antes da apresentação, para ter o 5.5 atualizado também - os comandos
estão documentados nos scripts, e o README antigo com os resultados do GPT-OSS-20B
permanece no histórico do Git para comparação.

## Limitação conhecida

A latência deixou de ser o problema principal depois da migração acima — de 130-180s por
chamada de LLM para 1-8s. O ponto de atenção agora é o "cold start" do modelo de
embeddings do RAG (ver adendo acima): a primeira chamada depois de um tempo ocioso pode
estourar 60 segundos de timeout. Mitigo com uma chamada de aquecimento antes de qualquer
demonstração ao vivo - mesma lógica de precaução que já usava desde a E3, só que agora
focada num ponto diferente do pipeline.
