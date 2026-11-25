# Vortex Analytics Copilot

Assistente interno da **Vortex Marketplace** para análise de dados sem precisar
esperar na fila do time de BI. Pergunte em português, como falaria com um
analista, e o sistema multiagente consulta o dicionário semântico e o banco
de dados (schema `dw`) para responder.

## O que você pode perguntar

- **Definições de métricas:** "O que é ticket médio?", "Como é calculada a
  margem de contribuição?"
- **Dados reais do negócio:** "Qual foi a receita de 2017?", "Quantos
  pedidos existem na base?"
- **Perguntas combinadas:** definição + dado na mesma pergunta.

## Como funciona por trás

Cada pergunta passa por um grafo de 5 agentes especializados (Orquestrador,
Semântico/RAG, Gerador de SQL, Validador, Execução e Resposta), com um
Validador determinístico que garante que só rodam consultas `SELECT` no
schema `dw` - nenhum dado é inventado, e toda resposta cita a fonte usada.

Projeto de estudo (Vortex Marketplace é uma empresa fictícia), construído
como parte do treinamento de Analytics sob Demanda.
