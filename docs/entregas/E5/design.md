# E5 — Design: Sistema Multi-Agente Orquestrado

Documento de design, escrito **antes** de implementar (mesmo processo das
entregas anteriores: entender e alinhar antes de codar). Depois que a E5
estiver pronta e testada, o `docs/entregas/E5/README.md` vai registrar o que
foi feito de fato, no mesmo formato de E1–E4 — este arquivo é o plano, não o
relatório final.

## Intenção e porquê

A E4 entregou **um agente só** que mistura, num único prompt, o papel do
Agente Semântico/RAG e do Agente de Execução da arquitetura da E1
(`docs/entregas/E1/README.md`), decidindo tudo via tool calling solto. A E5
pede para materializar os **5 agentes especializados** da E1 como peças
separadas, com um orquestrador de verdade coordenando o fluxo entre eles, um
estado compartilhado passando de agente em agente, e um Validador que analisa
o SQL de forma **determinística** — não só confiando no prompt, porque já
vimos na E4 que o modelo às vezes não segue 100% as regras escritas.

## Escopo (mapeado nos itens 5.1 a 5.5 do enunciado)

- **5.1** — os 5 agentes, cada um com uma função Python chamável e testável
  sozinho (não só dentro do grafo).
- **5.2** — o grafo LangGraph: ordem de execução, passagem de estado, arestas
  condicionais, loop de correção, tratamento de erro.
- **5.3** — o estado compartilhado (`AgentContext`) que cada nó lê e atualiza.
- **5.4** — uma demonstração ponta a ponta documentada (pergunta → cada
  agente → resposta final consolidada).
- **5.5** — bateria de testes de integração do fluxo completo, incluindo
  casos de borda.

## Goals

- Os 5 agentes da E1 existindo de verdade, cada um com responsabilidade
  única e testável isoladamente.
- Validador determinístico (sem LLM) usando `sqlglot` para análise estática
  real da árvore do SQL, não regex.
- Loop de correção formal: erro de validação ou de execução volta para o
  Gerador de SQL com o motivo, até um limite de tentativas.
- Reaproveitar ao máximo o que já funciona da E4 (`retrieve()` para o
  RAG, a lógica de `tool_consulta_banco` para a execução, a role
  `agente_leitura`) — a E5 reorganiza responsabilidades, não reescreve do
  zero o que já está testado.
- Testes de integração cobrindo o caminho feliz, a correção funcionando, e
  os casos de borda (limite de tentativas estourado, pergunta ambígua,
  pergunta que não precisa de SQL).

## Non-goals (fora do escopo desta entrega)

- API HTTP / FastAPI expondo o grafo (isso é a E6).
- Interface de usuário (E6).
- Métricas de avaliação formal / dataset de avaliação (E7).
- Resolver a latência do GPT-OSS-20B (~130-180s por chamada) — é uma
  limitação já aceita e documentada desde a E3, não um problema desta
  entrega.

## Anti-goals

- Não criar um 6º agente ou dividir "Execução" e "Resposta" em dois nós —
  a E1 já definiu esse par como **um** agente ("Execução e Resposta").
  Inventar uma divisão nova aqui quebraria a rastreabilidade com o que foi
  planejado e aprovado na E1.
- Não deixar o Validador depender de LLM "só pra garantir" — se o
  determinístico (`sqlglot`) achar que está ok, está ok; não tem segunda
  opinião de modelo nenhuma. É esse o ponto que torna esse agente diferente
  dos outros 4.

## Constraints

- Latência: cada chamada de LLM continua custando ~130-180s (fila do tier
  gratuito da NVIDIA, não é o tamanho da pergunta). Isso significa que o
  caminho feliz completo (Orquestrador → Gerador de SQL → Execução/Resposta)
  custa **3 chamadas de LLM**, e cada correção soma mais uma. Na prática é
  parecido com o que a E4 já tinha (2 a 5 rodadas do mesmo prompt pesado) —
  não piora o cenário, só reorganiza onde as chamadas acontecem. Mitigação:
  a mesma da E3/E4 — testes em segundo plano e respostas pré-computadas para
  qualquer demonstração ao vivo.
- Segurança: a role `agente_leitura` (somente leitura no Postgres) continua
  sendo a última linha de defesa, mesmo com o Validador. Defesa em
  profundidade, não substituição.
- Idioma e formato de resposta: português do Brasil, valores em R$ com 2
  casas, cita a fonte da definição usada — mesmas regras da E4.
- Nenhuma operação de escrita em nenhuma camada (nem o Gerador de SQL deve
  ser instruído a considerar isso uma opção).

## Approaches considerados

### Validador (decisão já fechada na conversa)

| Opção | Descrição | Trade-off |
|---|---|---|
| A — regex evoluído | Mesmas 5 checagens do `tools.py`, reorganizadas como nó determinístico | Simples, zero dependência nova, mas um SQL malicioso bem escondido (comentário escondendo `UNION`, por exemplo) ainda pode escapar |
| **B — `sqlglot` (escolhido)** | Faz parse da árvore SQL de verdade: tipo de statement, tabelas referenciadas, ausência de sub-statements perigosos | Mais robusto e mais correto para um agente de "análise estática" de verdade; custo é uma dependência nova (pequena, só para parsing) |

### Orquestrador — como ele classifica a intenção

| Opção | Descrição | Trade-off |
|---|---|---|
| **LLM leve (escolhido, minha decisão)** | Uma chamada de LLM dedicada, prompt curto, classifica a pergunta em 4 categorias (ver estado, abaixo) | Mantém a fidelidade ao desenho da E1 (é um agente de verdade, com raciocínio, não um `if` de palavra-chave); custa mais uma chamada de ~130-180s, mas está dentro do orçamento de latência já aceito |
| Heurística por palavra-chave | Decide por regras de texto (ex.: "o que é" → definição; "quanto", "quantos", "compare" → dado) | Mais rápido (sem chamada de LLM), mas frágil para perguntas reais em português natural, e descaracteriza o Orquestrador como agente |

### Execução e Resposta — como escreve a narrativa final

Sempre por LLM (uma chamada), porque é texto em linguagem natural citando
fonte — não tem lógica determinística sensata para isso. É o mesmo texto
final que a E4 já produzia, só que agora como responsabilidade de um nó
dedicado em vez de ser "o que sobra" do loop de tool calling.

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

Cada nó lê os campos que precisa, roda sua tarefa, e devolve só os campos que
mudou — o LangGraph cuida de mesclar no estado global (é assim que o
mecanismo de `StateGraph` funciona). `historico` existe para a demonstração
do 5.4 e para os testes do 5.5 conseguirem inspecionar o caminho percorrido
sem precisar reconstruir logs externos.

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

Toda rota termina em `execucao_resposta` — é sempre esse agente quem escreve
o texto final, seja ele baseado em dado real, só em definição do RAG, num
pedido de esclarecimento, ou numa explicação de falha (tentativas esgotadas).

**Trava de loop:** mesmo princípio do `MAX_RODADAS` da E4 — um limite de
tentativas (a decidir o número exato, provavelmente 3, na implementação) que,
ao estourar, força a rota para `execucao_resposta` em modo "não consegui
responder", em vez de tentar para sempre.

## Decisões adicionais (depois de uma revisão deste documento)

Três pontos onde um chute errado mudaria a estrutura do estado ou do código
de teste — resolvidos aqui, com o raciocínio, para não ficarem em aberto na
implementação:

1. **O contador de tentativas é um só, compartilhado entre os dois loops de
   correção** (reprovação do Validador **e** erro de execução do Postgres),
   não dois campos separados. Motivo: a E1 fala em "um limite de tentativas"
   no singular, e as duas situações gastam o mesmo recurso — uma nova rodada
   do Gerador de SQL. Mantém o `AgentContext` simples (só `tentativas: int`,
   como já estava desenhado) e segue o mesmo princípio do `MAX_RODADAS` único
   da E4.
2. **Os testes (5.1 e 5.5) rodam contra a LLM de verdade, não mockada** —
   mesmo padrão de E1 a E4, que nunca usaram mock de LLM, sempre bateria
   pequena e curada rodando de verdade (ex.: os 7 cenários do 4.4). Para não
   explodir em horas de execução: os testes individuais do 5.1 usam poucos
   casos por agente (2-3, o suficiente para provar que funciona isolado,
   não uma cobertura exaustiva), e a integração do 5.5 segue o mesmo
   tamanho de bateria da E4 (bateria pequena, cobrindo caminho feliz +
   correção + bordas). Ambos rodam em segundo plano, com respostas
   pré-computadas disponíveis para qualquer demonstração ao vivo — mitigação
   já usada desde a E3.
3. **O fluxo de "esclarecimento" termina a execução do script ali** — pede o
   esclarecimento em texto e acaba, sem loop de múltiplos turnos. Multi-turno
   de verdade (o usuário respondendo e o grafo continuando de onde parou) é
   trabalho de API/UI, que é a E6 — já está fora do escopo da E5 (ver
   non-goals). A E5 só precisa provar que o Orquestrador sabe identificar
   quando a pergunta é ambígua e que o grafo sabe terminar graciosamente
   nesse caso, igual a um `run_agent()` normal da E4 que devolve texto e
   acaba.

## O que fica para a implementação decidir

- Nome exato dos arquivos novos (ex.: `scripts/orquestrador.py`,
  `scripts/validador.py`, `scripts/gerador_sql.py`, e se `execucao_resposta`
  vira um arquivo novo ou uma evolução de `tools.py`/`agent.py`).
- Prompt exato de cada agente (Orquestrador, Gerador de SQL, Execução e
  Resposta) — seguem o espírito das regras já validadas no
  `AGENT_SYSTEM_PROMPT` da E4, adaptadas ao escopo mais estreito de cada um.
- Checagens exatas do Validador em `sqlglot` (quais tipos de statement
  aceitar, como confirmar que só tabelas `dw.*` são referenciadas).
- Número exato do limite de tentativas (padrão sugerido: 3).
- Formato exato dos testes de integração do 5.5 (reaproveitar o padrão do
  `scripts/run_agent_tests.py` da E4, adaptado para testar o grafo inteiro
  em vez do agente único) e quais casos de borda específicos entram na
  bateria.
