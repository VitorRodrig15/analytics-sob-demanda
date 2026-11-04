# E3 — Pipeline RAG Funcional

**Período:** 02/11 a 06/11/2026 · **Foco:** RAG · **Status:** ✅ Concluída

Entregáveis 3.1 a 3.5: módulo de recuperação, integração com a LLM, pipeline
RAG completo, prompt engineering e testes qualitativos.

## 3.1 Módulo de recuperação (Retrieval)

`scripts/search.py` — função `retrieve(pergunta, k=3, tipo=None)`: gera o
embedding da pergunta (tipo *query*) e busca os `k` chunks mais parecidos em
`rag.documents` por similaridade de cosseno. Usável tanto como CLI quanto
como módulo importado por outros scripts (é o que o pipeline do 3.3 faz).

## 3.2 Integração com a LLM

`scripts/test_llm.py` confirma a conexão com o **GPT-OSS-20B** via NVIDIA
NIM. Achado importante, investigado a fundo: cada chamada leva **130–180
segundos** neste endpoint, independente de tamanho de resposta, "esforço de
raciocínio" ou se é a 1ª ou a 2ª chamada — é uma limitação de fila do tier
gratuito da NVIDIA, não algo que o código controla. Documentado no topo do
script, com os 4 testes que descartaram outras causas (rede, modelo "frio",
tamanho do raciocínio).

## 3.3 Pipeline RAG end-to-end

`scripts/rag_pipeline.py` — função `ask(pergunta, k=3)` junta as peças:

```
pergunta → retrieve() [3.1] → build_messages() [3.4] → LLM [3.2] → resposta
```

Nesta etapa o agente responde **com base no dicionário** (explica métricas,
regras e exemplos, citando a fonte) — ele ainda não gera nem executa SQL de
verdade contra o banco `dw`; isso é o Agente Gerador de SQL e o Agente de
Execução, da E4/E5 em diante.

## 3.4 Prompt engineering

`scripts/prompts.py` — o `SYSTEM_PROMPT` define 7 regras fixas: responder só
com base no contexto, nunca inventar números, citar a fonte de cada
definição, explicar quando uma métrica é indisponível (ex.: margem de
contribuição), formatar valores em R$/%, responder em português direto, e
deixar claro que a execução de SQL ainda não está conectada. Inclui também
um **fato fixo** (a data de referência do projeto, 2018-08-31), adicionado
após um achado do 3.5 — ver abaixo.

## 3.5 Testes qualitativos

12 perguntas (acima do mínimo de 10), cobrindo as 4 intenções mais regra de
negócio, métrica indisponível, segurança e descrição de tabela. Relatório
completo: [docs/e3_testes_qualitativos.md](../../e3_testes_qualitativos.md).

| Critério | Resultado |
|---|---|
| Contexto relevante | 12/12 (100%) |
| Citou a fonte | 11/12 (92%) |
| Resposta correta | 11/12 (92%) — 10 completas, 1 parcial |
| Números inventados | 0/12 |

**Achado e correção:** em 2 das 12 perguntas, o agente usou uma data errada
(2026 e 2023) em vez da data de referência fixa do projeto (31/08/2018),
porque o chunk da regra de datas não entrava no top-3 de busca. Corrigido
adicionando a data como fato fixo no `SYSTEM_PROMPT` (em vez de depender só
da busca) e aumentando `max_tokens` de 800 para 1200 (uma resposta havia sido
cortada no meio). As 2 perguntas foram refeitas após a correção e passaram a
usar a data certa — resultado em
[docs/e3_reteste_correcao.jsonl](../../e3_reteste_correcao.jsonl).

## Evidências de execução real

- [docs/respostas_3.3_exemplo.jsonl](../../respostas_3.3_exemplo.jsonl) — 2
  perguntas de exemplo do pipeline end-to-end (3.3).
- [docs/e3_testes_qualitativos.jsonl](../../e3_testes_qualitativos.jsonl) —
  as 12 respostas brutas da bateria de testes (3.5).
- [docs/e3_testes_qualitativos.md](../../e3_testes_qualitativos.md) — o
  relatório de avaliação qualitativa, com o antes/depois da correção.
