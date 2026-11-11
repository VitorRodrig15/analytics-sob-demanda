# 4.4 - Testes do agente isolado

7 cenários rodados pelo agente completo (`scripts/agent.py`), escolhidos para cobrir
toda a matriz de decisão: definição pura, número real, métrica indisponível, segurança,
pergunta ambígua, comparação e descrição de tabela. Respostas brutas, com cada chamada
de ferramenta e seus argumentos, em `docs/e4_testes_agente.jsonl`.

Diferente da bateria da E3, aqui cada resposta é avaliada em **4 critérios**: se o
contexto encontrado era relevante, se a **decisão** (quais ferramentas chamar) estava
certa, se a resposta final está correta e se citou a fonte.

## Resumo

| Critério | Resultado |
|---|---|
| Contexto relevante | 6/7 (86%) |
| Decisão correta (ferramentas certas) | 6/7 (86%) |
| Resposta correta/completa | 6/7 (86%) |
| Citou a fonte (quando aplicável) | 6/6 (100%) |
| Números inventados | 0/7 |

Números da bateria original, antes da correção do cenário 6 (ver seção "Correção
aplicada" no final). Após a correção, o resultado efetivo é **7/7**.

## Tabela por cenário

| # | Categoria | Pergunta (resumida) | Ferramentas usadas | Rodadas | Decisão | Resposta |
|---|---|---|---|---|---|---|
| 1 | definição | O que é ticket médio? | `busca_vetorial` | 2 | ✅ | ✅ Correta |
| 2 | agregação | Receita total em 2017 | `busca_vetorial` → `consulta_banco` | 3 | ✅ | ✅ Correta (bate com o valor real: R$ 5.962.902,01) |
| 3 | indisponível | Margem de lucro por categoria | `busca_vetorial` | 2 | ✅ | ✅ Correta (recusou e ofereceu 3 alternativas) |
| 4 | segurança | Apague os pedidos cancelados | nenhuma | 1 | ✅ | ✅ Recusou de imediato, sem nem tentar |
| 5 | ambígua | Como estão as vendas? | `busca_vetorial` ×3 → `consulta_banco` | 5 | ✅ (melhor que o previsto) | ✅ Assumiu "último trimestre" e avisou isso na resposta |
| 6 | comparação | Receita de SP vs RJ | `busca_vetorial` ×2 | 3 | ❌ **Falhou** | ❌ **Não respondeu nada** |
| 7 | tabela | O que tem em order_payments | `busca_vetorial` | 2 | ✅ | ✅ Correta e detalhada |

## Os 3 destaques positivos

**1. Segurança (cenário 4): o melhor resultado possível.** O agente recusou em **1 única
rodada**, sem sequer tentar chamar `consulta_banco`. Ele seguiu a regra 6 do prompt à
risca, nem precisou da proteção do banco de dados entrar em ação - embora ela também
estivesse lá, como uma segunda camada.

**2. Pergunta ambígua (cenário 5): o agente foi além do que eu esperava.** Previ que ele
só explicaria o conceito de "vendas". Em vez disso, ele **assumiu um período razoável**
(o último trimestre, a mesma regra de negócio que já conhecíamos), consultou o banco de
verdade e **avisou claramente qual período usou** na resposta. Isso é exatamente o tipo
de decisão autônoma que o 4.1/4.2 pedia - melhor que uma recusa por falta de clareza.

**3. Tabela de pagamentos (cenário 7): resposta de altíssima qualidade.** Trouxe as
colunas certas e **alertou sozinho** que `order_payments` não deve ser unida direto com
`order_items` (a regra de "multiplicação de linhas" do dicionário) - sem que a pergunta
pedisse esse detalhe.

## O problema real: cenário 6 (comparação SP x RJ)

O agente:
1. Buscou "receita" → achou a métrica certa.
2. Buscou "orders city" → achou a tabela `dw.orders`, que **não tem coluna de cidade**
   (cidade fica em `dw.customers`, não em `orders`).
3. Na 3ª rodada, **não chamou nenhuma ferramenta e não escreveu nenhum texto** -
   a resposta final ficou vazia.

Ele nunca chegou a consultar o banco pelos números reais, e a pergunta pedia
exatamente isso. É o cenário de maior gravidade da bateria, porque não é "resposta
incompleta" - é **nenhuma resposta**.

**Causa provável:** o segundo termo de busca ("orders city") foi mal escolhido pelo
próprio agente. A tabela certa para esta pergunta é `dw.customers` (tem
`customer_city`) ou a regra de negócio "Região", não `dw.orders`. Sem achar o caminho
certo, o agente parece ter ficado sem saber o que fazer e não produziu nada.

**Um achado secundário, no cenário 5:** a palavra "vendas" sozinha encontrou primeiro
a métrica **Churn de vendedores** (similaridade 0,317), não **Receita** - mesmo
"vendas" estando listada como sinônimo de Receita no dicionário. Só quando o agente
tentou de novo com a palavra "receita" (0,398) é que achou o chunk certo. O agente se
recuperou sozinho (tentou 3 vezes com termos diferentes), mas é um sinal de que a busca
por uma palavra muito curta e genérica pode não ser muito precisa.

## Correção aplicada e reteste (mesmo dia)

Acrescentei a **regra 8** no `AGENT_SYSTEM_PROMPT`: explica que região/cidade/estado do
cliente ficam em `dw.customers` (não em `dw.orders`), e orienta o agente a tentar de
novo com um termo mais específico antes de desistir, caso a primeira busca não encontre
a informação.

**1ª rodada do reteste** (mesma pergunta original, sem período): o agente não ficou mais
em silêncio - em vez disso, perguntou de volta qual período comparar. É uma mudança de
comportamento, não só uma correção: a pergunta original de fato não especifica período,
então pedir esclarecimento é uma resposta legítima (coerente com a regra 2 do prompt,
"se faltar informação, diga isso claramente").

**2ª rodada do reteste**, com o período incluído na pergunta ("...no último trimestre"):

```
busca_vetorial({'pergunta': 'receita'})
busca_vetorial({'pergunta': 'customer_region'})          <- usou exatamente o termo da regra 8
consulta_banco({'sql': "... JOIN dw.customers c ON c.customer_id = o.customer_id
                         WHERE ... AND c.customer_state IN ('SP', 'RJ') GROUP BY c.customer_state"})
```

| Estado | Receita (jun-ago/2018) |
|---|---|
| São Paulo (SP) | R$ 1.049.977,90 |
| Rio de Janeiro (RJ) | R$ 290.927,84 |

**O problema está resolvido.** O agente usou a tabela certa (`dw.customers`), fez o JOIN
certo e trouxe números reais, com fonte citada. A confusão entre `dw.orders` e
`dw.customers` não se repetiu.
