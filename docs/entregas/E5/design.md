# E5 — Design: Sistema Multi-Agente Orquestrado

Documento de design, escrito **antes** de implementar — mesmo processo das
entregas anteriores, entender e alinhar antes de codar. Depois que a E5
estivesse pronta e testada, o `docs/entregas/E5/README.md` registraria o que
de fato foi feito, no mesmo formato de E1 a E4. Este arquivo é o plano, não
o relatório final.

## Intenção e porquê

A E4 entregou um agente só, que mistura num único prompt o papel do Agente
Semântico/RAG e do Agente de Execução da arquitetura que desenhei na E1
(`docs/entregas/E1/README.md`), decidindo tudo via tool calling solto. A E5
pede para materializar os 5 agentes especializados da E1 como peças de fato
separadas, com um orquestrador de verdade coordenando o fluxo entre eles, um
estado compartilhado passando de agente em agente, e um Validador que
analisa o SQL de forma determinística — não só confiando no prompt, porque a
E4 já mostrou que o modelo às vezes não segue 100% as regras escritas.

## Escopo

O enunciado pede os itens 5.1 a 5.5, e é assim que mapeei cada um:

- **5.1** — os 5 agentes, cada um com uma função Python chamável e testável
  sozinho, não só dentro do grafo.
- **5.2** — o grafo LangGraph: ordem de execução, passagem de estado, arestas
  condicionais, loop de correção, tratamento de erro.
- **5.3** — o estado compartilhado (`AgentContext`) que cada nó lê e
  atualiza.
- **5.4** — uma demonstração ponta a ponta documentada, da pergunta até a
  resposta final consolidada, passando por cada agente.
- **5.5** — uma bateria de testes de integração do fluxo completo, incluindo
  casos de borda.

## Goals

Quero os 5 agentes da E1 existindo de verdade, cada um com responsabilidade
única e testável isoladamente. Quero um Validador determinístico, sem LLM,
usando `sqlglot` para analisar a árvore real do SQL — não regex. Quero um
loop de correção formal: erro de validação ou de execução volta para o
Gerador de SQL com o motivo, até um limite de tentativas. E quero reaproveitar
ao máximo o que já funciona da E4 — o `retrieve()` do RAG, a lógica de
`tool_consulta_banco` para a execução, a role `agente_leitura` — porque a E5
reorganiza responsabilidades, não reescreve do zero o que já está testado.
Os testes de integração precisam cobrir o caminho feliz, a correção
funcionando de verdade, e os casos de borda: limite de tentativas estourado,
pergunta ambígua, pergunta que não precisa de SQL.

## Non-goals

API HTTP ou interface de usuário expondo o grafo ficam para a E6. Métricas de
avaliação formal e dataset de avaliação ficam para a E7. E resolver a
latência do GPT-OSS-20B (130 a 180 segundos por chamada) não é problema desta
entrega — é uma limitação já aceita e documentada desde a E3.

## Anti-goals

Não vou criar um sexto agente nem dividir "Execução" e "Resposta" em dois
nós — a E1 já definiu esse par como um agente só ("Execução e Resposta"), e
inventar uma divisão nova aqui quebraria a rastreabilidade com o que foi
planejado e aprovado lá. Também não vou deixar o Validador depender de LLM
"só pra garantir": se o determinístico (`sqlglot`) achar que está ok, está
ok, sem segunda opinião de modelo nenhuma. É esse o ponto que torna esse
agente diferente dos outros 4.

## Constraints

A latência continua sendo a mesma: cada chamada de LLM custa de 130 a 180
segundos, fila do tier gratuito da NVIDIA, não o tamanho da pergunta. Isso
significa que o caminho feliz completo (Orquestrador → Gerador de SQL →
Execução/Resposta) já custa 3 chamadas, e cada correção soma mais uma. Na
prática fica parecido com o que a E4 já tinha (2 a 5 rodadas do mesmo prompt
pesado) — não piora o cenário, só reorganiza onde as chamadas acontecem.
Mitigo do mesmo jeito que na E3/E4: testes em segundo plano e respostas
pré-computadas para qualquer demonstração ao vivo.

Em segurança, a role `agente_leitura` (somente leitura no Postgres) continua
sendo a última linha de defesa, mesmo com o Validador — defesa em
profundidade, não substituição. O idioma e o formato de resposta seguem as
mesmas regras da E4: português do Brasil, valores em R$ com 2 casas, citando
a fonte da definição usada. E nenhuma camada pode escrever nada — nem o
Gerador de SQL deve ser instruído a considerar isso uma opção.

## Approaches considerados

Para o Validador, essa decisão eu já tinha fechado durante a conversa:

| Opção | Descrição | Trade-off |
|---|---|---|
| A — regex evoluído | Mesmas 5 checagens do `tools.py`, reorganizadas como nó determinístico | Simples, zero dependência nova, mas um SQL malicioso bem escondido (um comentário escondendo um `UNION`, por exemplo) ainda pode escapar |
| **B — `sqlglot` (escolhido)** | Parse da árvore SQL de verdade: tipo de statement, tabelas referenciadas, ausência de sub-statements perigosos | Mais robusto e mais correto para um agente de "análise estática" de verdade; custa uma dependência nova, pequena, só para parsing |

Para o Orquestrador, a dúvida era como ele classifica a intenção da pergunta:

| Opção | Descrição | Trade-off |
|---|---|---|
| **LLM leve (escolhido, minha decisão)** | Uma chamada de LLM dedicada, prompt curto, classificando a pergunta em 4 categorias (ver estado, abaixo) | Mantém a fidelidade ao desenho da E1 — é um agente de verdade, com raciocínio, não um `if` de palavra-chave; custa mais uma chamada de 130 a 180s, mas dentro do orçamento de latência já aceito |
| Heurística por palavra-chave | Decide por regras de texto ("o que é" → definição; "quanto", "quantos", "compare" → dado) | Mais rápido, sem chamada de LLM, mas frágil para perguntas reais em português natural, e descaracteriza o Orquestrador como agente |

Para a narrativa final do agente de Execução e Resposta, nem cheguei a
considerar alternativa: sempre por LLM, numa chamada só, porque é texto em
linguagem natural citando fonte — não existe lógica determinística sensata
para isso. É o mesmo texto final que a E4 já produzia, só que agora como
responsabilidade de um nó dedicado, em vez de ser "o que sobra" do loop de
tool calling.

## Estado compartilhado — `AgentContext`

```python
@dataclass
class AgentContext:
    pergunta: str
    intencao: str | None = None          # "definicao" | "dado" | "ambas" | "esclarecimento"
    contexto_rag: list[dict] = field(default_factory=list)
    sql_gerado: str | None = None
    validacao_ok: bool | None = None
    motivo_rejeicao: str | None = None    # do Validador
    resultado_execucao: dict | None = None
    erro_execucao: str | None = None      # do Postgres
    resposta_final: str = ""
    tentativas: int = 0                   # conta voltas ao Gerador de SQL
    historico: list[str] = field(default_factory=list)  # log passo a passo, para os testes/5.4
```

Cada nó lê os campos que precisa, roda sua tarefa, e devolve só o que mudou —
é o próprio mecanismo do `StateGraph` do LangGraph que cuida de mesclar isso
de volta no estado global. O `historico` existe justamente para a
demonstração do 5.4 e para os testes do 5.5 conseguirem inspecionar o
caminho percorrido sem precisar reconstruir logs externos.

## O grafo

```
                         ┌──────────────┐
                         │ orquestrador │
                         └──────┬───────┘
              esclarecimento    │   definicao / dado / ambas
              ┌─────────────────┘
              │                 │
              ▼                 ▼
    ┌───────────────────┐  ┌───────────────┐
    │ execucao_resposta  │  │ semantico_rag │
    │ (pede esclarecim.) │  └───────┬───────┘
    └────────────────────┘          │ definicao
                         ┌───────────┴───────────┐
                         │                       │ dado / ambas
                         ▼                       ▼
               ┌────────────────────┐   ┌───────────────┐
               │ execucao_resposta   │   │  gerador_sql  │
               │ (responde só c/ RAG)│   └───────┬───────┘
               └─────────────────────┘           │
                                                  ▼
                                          ┌───────────────┐
                                     ┌───►│   validador   │
                                     │    └───────┬───────┘
                          reprova,            aprova
                       tentativas<MAX             │
                                     │             ▼
                              ┌──────┴───┐  ┌────────────────────┐
                              │gerador_sql│  │ execucao_resposta  │
                              │(com motivo)│ │ (roda o SQL + narra)│
                              └───────────┘  └─────────┬──────────┘
                                                        │ erro do Postgres,
                                                        │ tentativas<MAX
                                                        ▼
                                                  ┌───────────┐
                                                  │gerador_sql│
                                                  │(com erro) │
                                                  └───────────┘
```

Toda rota termina em `execucao_resposta`: é sempre esse agente quem escreve
o texto final, seja ele baseado em dado real, só na definição do RAG, num
pedido de esclarecimento, ou numa explicação de falha quando as tentativas
se esgotam.

**Trava de loop:** mesmo princípio do `MAX_RODADAS` da E4 — um limite de
tentativas (a decidir o número exato na implementação, provavelmente 3) que,
ao estourar, força a rota para `execucao_resposta` em modo "não consegui
responder", em vez de tentar para sempre.

## Decisões adicionais

Depois de uma revisão deste documento, fechei três pontos onde um chute
errado mudaria a estrutura do estado ou do código de teste. Prefiro resolver
aqui, com o raciocínio registrado, do que deixá-los em aberto na
implementação.

O contador de tentativas é um só, compartilhado entre os dois loops de
correção — reprovação do Validador e erro de execução do Postgres — e não
dois campos separados. A E1 fala em "um limite de tentativas" no singular, e
as duas situações gastam o mesmo recurso: uma nova rodada do Gerador de SQL.
Isso mantém o `AgentContext` simples (só `tentativas: int`, como já estava
desenhado) e segue o mesmo princípio do `MAX_RODADAS` único da E4.

Os testes do 5.1 e do 5.5 rodam contra a LLM de verdade, nunca mockada —
mesmo padrão de E1 a E4, que nunca usaram mock de LLM, sempre bateria pequena
e curada rodando de verdade (os 7 cenários da 4.4, por exemplo). Pra não
explodir em horas de execução, os testes individuais do 5.1 usam poucos casos
por agente — 2 a 3, o suficiente para provar que funciona isolado, não uma
cobertura exaustiva — e a integração do 5.5 segue o mesmo tamanho de bateria
da E4: pequena, cobrindo caminho feliz, correção e bordas. Os dois rodam em
segundo plano, com respostas pré-computadas disponíveis para qualquer
demonstração ao vivo — mitigação que já uso desde a E3.

E o fluxo de "esclarecimento" termina a execução do script ali mesmo: pede o
esclarecimento em texto e acaba, sem loop de múltiplos turnos. Um
multi-turno de verdade — o usuário respondendo e o grafo continuando de onde
parou — é trabalho de API/UI, ou seja, da E6, já fora do escopo da E5 (ver
non-goals). A E5 só precisa provar que o Orquestrador sabe identificar quando
a pergunta é ambígua e que o grafo sabe terminar graciosamente nesse caso,
igual a um `run_agent()` normal da E4 que devolve texto e acaba.

## O que fica para a implementação decidir

Ficam abertos para a hora de codar: o nome exato dos arquivos novos (algo
como `scripts/orquestrador.py`, `scripts/validador.py`,
`scripts/gerador_sql.py`, e se `execucao_resposta` vira um arquivo novo ou
uma evolução de `tools.py`/`agent.py`); o prompt exato de cada agente
(Orquestrador, Gerador de SQL, Execução e Resposta), seguindo o espírito das
regras já validadas no `AGENT_SYSTEM_PROMPT` da E4, adaptadas ao escopo mais
estreito de cada um; as checagens exatas do Validador em `sqlglot` (quais
tipos de statement aceitar, como confirmar que só tabelas `dw.*` são
referenciadas); o número exato do limite de tentativas (sugiro 3 como
padrão); e o formato exato dos testes de integração do 5.5, reaproveitando o
padrão do `scripts/run_agent_tests.py` da E4 mas adaptado para testar o grafo
inteiro em vez do agente único, com os casos de borda específicos a definir
na bateria.
