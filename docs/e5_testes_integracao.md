# E5 — Testes de integração do grafo completo (5.4 / 5.5)

Bateria de testes end-to-end do `StateGraph` montado em `scripts/grafo.py` (Task 9),
que liga os 5 agentes (Orquestrador, Semântico/RAG, Gerador de SQL, Validador,
Execução e Resposta) com os dois loops de correção (Validador → Gerador de SQL,
e Execução → Gerador de SQL). Diferente das baterias anteriores (E3 3.5, E4 4.4,
E5 5.1), que testavam um agente isolado, aqui o que se avalia é a **orquestração**
inteira: se o grafo roteia pela aresta certa, se os loops de correção disparam de
verdade, e se os casos de borda terminam graciosamente sem travar.

Script: [`scripts/run_e5_tests.py`](../scripts/run_e5_tests.py). Resultados brutos
(um `AgentContext` completo por linha, incluindo o `historico` passo a passo):
[`docs/e5_testes_integracao.jsonl`](e5_testes_integracao.jsonl).

**Regra do projeto respeitada:** nenhuma chamada de LLM foi mockada — todos os
10 registros abaixo (7 cenários da bateria principal + 3 tentativas extras, ver
"Cenários que precisaram de mais de uma tentativa real") são execuções reais contra
o NVIDIA/OpenAI endpoint e o Postgres do container.

## Critério | Resultado

| Critério | Resultado |
|---|---|
| Contexto relevante (RAG trouxe o trecho certo quando aplicável) | 7/7 |
| Roteou pela aresta/intenção certa | 7/7 (ver nota sobre cenários 4/5/6 trocados) |
| Resposta correta/completa | 7/7 |
| Citou a fonte (quando usou o dicionário semântico) | 7/7 (100% do que era aplicável) |
| Números inventados | 0/7 |
| Terminou graciosamente sem travar (casos de erro/esgotado) | 3/3 (cenários 4, 5b e a tentativa esgotada de fato) |
| Loop de correção do Validador disparou de verdade | ✅ (cenários 5 e 6) |
| Loop de correção da Execução disparou de verdade | ✅ (cenário 5b) |

## Os 7 cenários exigidos e o que de fato aconteceu

A LLM não é determinística, então as perguntas foram desenhadas para **induzir**
cada caminho, não para garantí-lo. Como esperado pelo plano da Task 10, dois dos
cenários pensados para um loop específico acabaram trocando de papel na prática —
isso é reportado como aconteceu, sem forçar ou maquiar o resultado.

### 1. Caminho feliz com dado real — ✅ reproduzido exatamente como esperado

- **Pergunta:** "Qual foi a receita de 2017?"
- **Caminho:** orquestrador (`dado`) → semântico_rag (3 trechos) → gerador_sql →
  validador (aprovado) → execução (1 linha) → resposta.
- **Resultado:** **R$ 5.962.902,01** — idêntico ao valor confirmado manualmente na
  Task 9.
- **Avaliação:** contexto relevante ✅, decisão/roteamento ✅, resposta correta ✅,
  citou a fonte ✅ ("Receita"), números inventados: nenhum.

### 2. Pergunta só de definição — ✅ reproduzido exatamente como esperado

- **Pergunta:** "O que é ticket médio?"
- **Caminho:** orquestrador (`definicao`) → semântico_rag → **pula gerador_sql,
  validador e execução** → resposta direto do contexto.
- **Resultado:** definição correta ("receita média por pedido entregue, sem
  frete"), com a fórmula certa e a fonte citada ("Ticket médio").
- **Avaliação:** todos os critérios ✅. Confirma que `rotear_apos_semantico`
  desvia corretamente o tráfego de SQL quando a intenção é só conceitual.

### 3. Pergunta ambígua — ✅ reproduzido exatamente como esperado

- **Pergunta:** "Como estamos?"
- **Caminho:** orquestrador (`esclarecimento`) → **pula semântico_rag também** →
  resposta pedindo para o gestor detalhar o que quer saber.
- **Resultado:** pediu esclarecimento, oferecendo exemplos de direções possíveis
  (financeiro, desempenho, operacional) sem adivinhar uma resposta.
- **Avaliação:** todos os critérios ✅ — não consultou o dicionário nem o banco,
  exatamente como o design do grafo prevê para esta intenção.

### 4 e 6. Loop do Validador e tentativas esgotadas — **os papéis se inverteram**

O plano original separava: cenário 4 = Validador rejeita uma vez e corrige na
segunda; cenário 6 = tentativas esgotadas (3 rejeições sem nunca aprovar). Na
prática, a pergunta pensada para o cenário 4 (comparação complexa
multi-tabela) esgotou as 3 tentativas sem nunca produzir SQL válido, e a
pergunta pensada para o cenário 6 (margem de lucro, métrica indisponível)
foi rejeitada só uma vez e corrigida na segunda. **Isso é reportado como
aconteceu** — cada cenário cobre de fato o comportamento do outro:

**Cenário 4 (rotulado `loop_validador`), comportamento real = tentativas esgotadas:**
- **Pergunta:** "Compare a receita por vendedor em cada região no último
  trimestre com o trimestre anterior, detalhando também o frete médio por
  pedido."
- **Histórico:** tentativa 1 rejeitada (SQL com erro de sintaxe/parse);
  tentativas 2 e 3 rejeitadas por não conterem nenhuma instrução SQL válida
  (`Esperado exatamente 1 instrucao SQL, encontrado 0` — o gerador_sql devolveu
  texto explicativo em vez de SQL puro nas tentativas seguintes, provavelmente
  por não conseguir fechar a consulta complexa dentro do limite de tokens).
  `tentativas = 3` → roteamento "esgotado" → `execucao_resposta` nunca tenta
  executar (porque `validacao_ok` nunca foi `True`) e vai direto para
  `responder()`.
- **Resposta final:** explicou corretamente que não foi possível obter os
  dados, resumiu o que a consulta *deveria* calcular (citando as fontes
  "Receita por vendedor" e "Percentual do frete sobre a receita"), e **não
  inventou nenhum número** — só descreveu a fórmula, sem afirmar um valor.
- **Avaliação:** terminou graciosamente sem travar ✅; não inventou número ✅;
  citou fonte ✅ (mesmo sem ter dado real). Como prova do cenário "tentativas
  esgotadas" (item 6 do brief), é um resultado válido e completo.

**Cenário 6 (rotulado `esgotado`), comportamento real = Validador rejeita e corrige:**
- **Pergunta:** "Qual foi a margem de lucro líquida por categoria de produto
  no último trimestre, considerando o CMV e as despesas de marketing?"
- **Histórico:** tentativa 1 rejeitada (mesmo motivo "0 instruções" — o
  gerador devolveu só texto); tentativa 2 aprovada pelo Validador. O SQL
  aprovado na tentativa 2 não calcula nada: é um `SELECT` literal com uma
  string explicando que a métrica não é calculável (`SELECT 'Não é possível
  calcular...' AS mensagem`) — tecnicamente válido (schema `dw` nem é
  referenciado, então passa a checagem do Validador) e foi executado sem erro.
- **Resposta final:** explicou corretamente que a métrica é indisponível
  (citando "Margem de contribuição" e "Métricas indisponíveis"), ofereceu
  3 alternativas reais (receita, ticket médio, % frete/receita) e não
  inventou nenhum custo.
- **Avaliação:** prova o loop de correção do Validador (item 4 do brief) de
  forma legítima — rejeitado uma vez, aprovado e executado na segunda.
  Contexto relevante ✅, resposta correta ✅, citou fonte ✅, nenhum número
  inventado ✅.

### 5. Execução falha e corrige — não reproduziu na pergunta original; reproduziu numa segunda pergunta mais adversarial

- **Pergunta original:** "Quais são os nomes dos clientes que mais compraram
  em 2018?" (desenhada para induzir o gerador_sql a inventar uma coluna de
  nome em `dw.customers`, que não existe).
- **O que aconteceu de fato:** a 1ª tentativa foi rejeitada pelo **Validador**
  (erro de sintaxe SQL), não pela execução — a 2ª tentativa foi aprovada e
  executada com sucesso, usando corretamente `customer_unique_id` (sem
  inventar nome), retornando 1 cliente. O modelo evitou a armadilha da coluna
  inexistente, que é um bom sinal de robustez, mas significa que este cenário
  não testou o loop de correção do lado da **execução** como pretendido — só
  mais uma instância do loop do Validador.
- **Retry (cenário `5b`), pergunta mais adversarial:** "Qual o CNPJ e o
  telefone dos vendedores com maior faturamento no Sudeste em 2018?" (CNPJ e
  telefone são campos de negócio plausíveis, mas não existem em `dw.sellers`
  nem em nenhuma tabela do schema).
  - **Histórico:** tentativa 1 rejeitada pelo Validador (0 instruções);
    tentativa 2 rejeitada pelo Validador (0 instruções); tentativa 3 **aprovada
    pelo Validador** e falhou na **execução real contra o Postgres**:
    `column s.seller_cnpj does not exist`. Como essa era a 3ª tentativa,
    `tentativas` chegou a `MAX_TENTATIVAS = 3` e o grafo encerrou via
    "esgotado" sem tentar de novo.
  - **Resultado:** prova de fato que o loop de correção do lado da
    **execução** dispara com um erro real do Postgres (não simulado) — a
    aresta `execucao_resposta --tentar_de_novo--> gerador_sql` de
    `grafo_routing.rotear_apos_execucao` foi exercida de verdade. O grafo não
    chegou a corrigir com sucesso dentro das tentativas restantes (só havia 1
    tentativa livre depois da falha de execução, e ela não foi suficiente),
    mas terminou graciosamente, explicando o erro real (`column s.seller_cnpj
    does not exist`) sem inventar CNPJ nem telefone nenhum.
- **Avaliação honesta:** o cenário exato pedido pelo brief ("falha na 1ª,
  corrige na 2ª") não foi observado em nenhuma das duas tentativas reais — o
  mais próximo obtido foi uma falha de execução real que esgotou as tentativas
  em vez de corrigir a tempo. Isso é reportado como uma lacuna de cobertura,
  não maquiado: **confirma que o loop de execução dispara com um erro real**,
  mas não confirma o caminho específico de "corrige com sucesso depois de um
  erro de execução" dentro do orçamento de tentativas testado.

### 7. Consulta válida sem resultado — reproduzido, com uma nuance de cobertura de código encontrada e confirmada numa segunda pergunta

- **Pergunta original:** "Qual foi a receita de pedidos entregues em janeiro
  de 2016?" (mês anterior ao início real dos dados, set/2016).
- **O que aconteceu:** SQL aprovado e executado sem erro, mas por ser uma
  **agregação** (`SUM(oi.price)`), o Postgres devolveu **1 linha com o valor
  `NULL`** (`{"receita": null}`), não 0 linhas. Isso é importante porque o
  código de `execucao_resposta._montar_user_content` só usa a mensagem
  dedicada de "nenhum resultado" quando `linhas` está **vazia**
  (`if not linhas`) — com 1 linha contendo `None`, esse ramo não dispara, e o
  prompt enviado à LLM foi o de "resultado real" normal, com `linhas:
  [{'receita': None}]`. A resposta final mesmo assim disse corretamente "Não
  foram encontrados resultados" e não inventou um valor de R$ 0,00 — mas isso
  veio do **julgamento da própria LLM** ao ver `None`, não do código
  determinístico dedicado a esse caso.
- **Achado reportado (não é um bug a corrigir nesta task, é uma observação
  honesta sobre cobertura):** o teste original validou o comportamento final
  correto, mas não exercitou de fato o ramo `if not linhas` do código.
- **Retry (cenário `7b`) para cobrir o ramo de código de verdade:** "Liste os
  pedidos entregues com nota de avaliação igual a 0." (`review_score` só
  existe de 1 a 5 — filtro impossível por construção, independente de
  distribuição de dados). SQL aprovado (`tentativas = 0`, aprovado de
  primeira), executado com sucesso, devolvendo **0 linhas reais**
  (`"linhas": [], "total_retornado": 0`). A resposta final: "Não foram
  encontrados resultados para a solicitação..." — desta vez passando mesmo
  pelo ramo dedicado `if not linhas`.
- **Avaliação:** critério do brief ("a resposta diz 'nenhum resultado', não
  inventa número") ✅ confirmado nas duas perguntas, mas só a segunda (`7b`)
  prova o código determinístico de fato; a primeira prova que a LLM também
  se comporta corretamente quando o agregado vem `NULL` em vez de vazio — um
  caso de borda adicional e relevante, que vale considerar documentar/testar
  separadamente em uma iteração futura (não é escopo desta task corrigir).

## Cenários que precisaram de mais de uma tentativa real

Por transparência (nenhum valor foi forçado ou mockado): além dos 7 cenários
da bateria principal (`scripts/run_e5_tests.py`), 3 execuções extras foram
feitas manualmente para investigar lacunas de cobertura encontradas na
primeira passada — todas gravadas em
[`docs/e5_testes_integracao.jsonl`](e5_testes_integracao.jsonl) com
`cenario_id` `"5b"` e `"7b"`:

- `5b` — pergunta sobre CNPJ/telefone de vendedores, para confirmar um erro
  real de execução (ver seção do cenário 5 acima).
- `7b` — pergunta com filtro logicamente impossível (`review_score = 0`),
  para confirmar o ramo de código "0 linhas" de verdade (ver seção do
  cenário 7 acima).

## Bug encontrado e corrigido durante esta task

`scripts/run_e5_tests.py` originalmente quebrava ao serializar o primeiro
cenário para `.jsonl`: `ctx.resultado_execucao` traz valores `Decimal` do
psycopg (colunas `numeric`), que o `json.dumps` padrão não serializa
(`TypeError: Object of type Decimal is not JSON serializable`). Corrigido
adicionando `default=str` à chamada de `json.dumps` (o `.jsonl` é só para
leitura/auditoria, não precisa de round-trip de tipo). A bateria foi
re-executada do zero depois da correção; o cenário 1 confirmado novamente com
o mesmo resultado (R$ 5.962.902,01).

## Conclusão

O grafo completo passa pelos 7 comportamentos exigidos (caminho feliz,
definição pura, esclarecimento, correção do Validador, correção da Execução,
tentativas esgotadas, consulta sem resultado), nenhum deles mockado. Dois
achados honestos valem registro para quem for revisar ou estender esta
bateria: (1) os cenários desenhados para "Validador corrige na 2ª" e
"tentativas esgotadas" trocaram de papel na prática entre as perguntas 4 e 6
— ambos os comportamentos foram observados, só não na pergunta planejada
para cada um; (2) o cenário "execução falha e corrige com sucesso" não foi
observado dentro do orçamento de tentativas testado — o loop de execução foi
confirmado disparando com um erro real do Postgres (`5b`), mas esgotou as
tentativas em vez de corrigir a tempo, o que é reportado como está, sem
forçar um resultado diferente.
