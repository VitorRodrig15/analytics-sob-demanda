"""Entregável 3.4 (E3) - Prompt engineering inicial: system prompt + contexto.

Este arquivo define como a pergunta do gestor e os chunks recuperados (3.1)
se encaixam antes de ir para a LLM (3.2). Nesta etapa do projeto, o agente
ainda responde com base só no DICIONÁRIO (explica métricas, regras, tabelas
e exemplos, citando a fonte) - ele ainda não gera nem executa SQL de
verdade no banco dw. Isso entra com o Agente Gerador de SQL e o Agente de
Execução, na E4/E5.

Dois blocos fazem o trabalho:
  SYSTEM_PROMPT    - as instrucoes fixas, que valem pra toda conversa
  build_messages() - monta a lista de mensagens (system + user) pronta
                      para client.chat.completions.create(messages=...)

O SYSTEM_PROMPT passou por um ajuste no mesmo dia em que escrevi: depois
dos testes qualitativos (3.5) mostrarem o agente usando datas erradas
(2026 e 2023 em vez de 2018, a referencia fixa do projeto), acrescentei a
data direto aqui como um fato que nao depende da busca encontrar o chunk
certo. Tambem reforcei a regra de citacao de fonte e a de nao mostrar SQL
sem pedido - um lembrete de que um modelo de linguagem nao obedece 100% uma
regra de prompt so porque ela esta escrita, por mais clara que seja.

Uso como modulo (de outro script em scripts/):
    from prompts import build_messages
    messages = build_messages(pergunta, chunks)

Uso como CLI, para ver o prompt montado sem chamar a LLM (ela demora
~150s por chamada - ver a nota de latencia em test_llm.py). Esse e o
comando mais seguro pra demonstrar ao vivo, porque e instantaneo:
    docker compose exec app python scripts/prompts.py "qual o ticket medio?"
"""
import argparse
import sys

from search import retrieve

SYSTEM_PROMPT = """\
Você é o assistente de analytics da Vortex Marketplace, um marketplace \
B2C brasileiro. Você ajuda gestores de negócio que não sabem SQL a \
entender métricas e dados da empresa.

Fato fixo, válido sempre, não depende do contexto recuperado: a data de \
referência ("hoje") para qualquer cálculo de período é 2018-08-31. \
"Este ano" = 2018. "Último trimestre" = 01/06/2018 a 31/08/2018. Nunca \
use a data real de hoje nem outro ano (como o ano atual do calendário) \
para isso — os dados do projeto só existem até 31/08/2018.

Regras que você deve seguir sempre:
1. Responda SOMENTE com base no contexto fornecido abaixo. Nunca use \
conhecimento próprio sobre a Vortex ou invente números, fórmulas ou \
nomes de tabela que não estejam no contexto.
2. Se o contexto não tiver a informação necessária para responder, diga \
isso claramente, não tente adivinhar. Explique o que falta.
3. OBRIGATÓRIO em toda resposta que usar uma definição do contexto: cite \
de onde ela veio, no formato "(fonte: <título do chunk>)" ao final do \
trecho correspondente. Uma resposta sem nenhuma citação está incompleta \
e não deve ser enviada assim.
4. Se o contexto disser que uma métrica é indisponível (como margem de \
contribuição), explique por que não é possível calculá-la e sugira uma \
métrica disponível no lugar, em vez de estimar um valor.
5. Valores em reais devem aparecer como "R$ X,XX" (2 casas decimais); \
percentuais como "X,XX%". NÃO inclua blocos de código SQL na resposta, \
a não ser que a pergunta do gestor peça explicitamente "a consulta", "o \
SQL" ou "a query". Fora isso, explique em texto o que a consulta faz.
6. Responda sempre em português do Brasil, em texto corrido e direto, \
sem embromação. Perguntas de negócio merecem respostas de negócio, não \
uma aula de banco de dados.
7. Você está nesta etapa do projeto só explicando o conhecimento do \
dicionário semântico — a execução de SQL no banco de dados real é uma \
etapa futura, ainda não disponível. Se o gestor pedir um número exato \
que dependeria de rodar uma consulta, explique a fórmula e avise que a \
consulta em si ainda não está conectada.\
"""

# Cabecalho de cada chunk no bloco de contexto: identifica a fonte para a
# citacao (regra 3 do system prompt, que agora e obrigatoria) e deixa claro
# o tipo de conhecimento que esta chegando pra LLM.
_TIPO_LABEL = {
    "metric": "Métrica",
    "business_rule": "Regra de negócio",
    "table_schema": "Tabela",
    "sql_example": "Exemplo de pergunta validada",
}


def format_context(chunks) -> str:
    """Formata os chunks recuperados num bloco de texto para o prompt."""
    if not chunks:
        return "(nenhum chunk relevante foi encontrado para esta pergunta)"

    blocos = []
    for chunk in chunks:
        label = _TIPO_LABEL.get(chunk.doc_type, chunk.doc_type)
        blocos.append(
            f"[Fonte: {chunk.title} | {label} | similaridade {chunk.similarity:.2f}]\n"
            f"{chunk.content}"
        )
    return "\n\n---\n\n".join(blocos)


def build_messages(pergunta: str, chunks) -> list[dict]:
    """Monta a lista de mensagens (system + user) para a chamada da LLM."""
    contexto = format_context(chunks)
    user_message = (
        f"Contexto recuperado do dicionário semântico:\n\n{contexto}\n\n"
        f"---\n\nPergunta do gestor: {pergunta}"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pergunta")
    parser.add_argument("--k", type=int, default=3, help="quantidade de chunks (padrao 3)")
    args = parser.parse_args()

    chunks = retrieve(args.pergunta, k=args.k)
    messages = build_messages(args.pergunta, chunks)

    for msg in messages:
        print(f"=== {msg['role'].upper()} ===")
        print(msg["content"])
        print()

    total_chars = sum(len(m["content"]) for m in messages)
    print(f"(tamanho total do prompt: {total_chars} caracteres, ~{total_chars // 4} tokens estimados)")


if __name__ == "__main__":
    main()
