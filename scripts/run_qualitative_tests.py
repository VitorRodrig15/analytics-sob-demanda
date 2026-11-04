"""Entregável 3.5 (E3) - Bateria de testes qualitativos do pipeline RAG.

Depois de ter o pipeline (3.3) e o prompt (3.4) prontos, faltava provar que
tudo isso funciona de verdade, não só na teoria. Este script roda 12
perguntas (passei do mínimo de 10 pedido pelo entregável) pelo pipeline
end-to-end e salva cada resposta, pra eu avaliar depois, com calma, em 3
critérios: correção, relevância do contexto recuperado e citação de fontes.

Escolhi as perguntas de propósito para cobrir situações bem diferentes: as
4 intenções do dicionário (agregação, comparação, tendência, ranking), mais
uma regra de negócio, uma métrica indisponível (margem de lucro), uma
pergunta de segurança e uma sobre o que tem numa tabela - pra testar o
agente em cenários variados, não só nas perguntas "fáceis" que eu sei que
vão dar certo.

Foi rodando esta bateria que encontrei os dois problemas mais sérios da
semana (datas erradas e uma resposta cortada por falta de tokens) - os dois
já documentados e corrigidos no system prompt (3.4) e no rag_pipeline.py.

LATÊNCIA: cada pergunta leva ~130-180s, então a bateria toda leva uns 25-35
minutos. Por isso rodo isto em segundo plano, e o script salva cada
resultado assim que fica pronto, sem esperar o final pra gravar - se algo
travar no meio, não perco o que já foi respondido.

Uso (dentro do container):
    docker compose exec app python scripts/run_qualitative_tests.py
"""
import json
import time
from dataclasses import asdict
from pathlib import Path

from rag_pipeline import ask

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "e3_testes_qualitativos.jsonl"

# (pergunta, intencao/categoria - so para organizar o relatorio depois)
PERGUNTAS = [
    ("Qual foi a receita total em 2017?", "agregacao"),
    ("Qual o ticket médio deste ano?", "agregacao"),
    ("Qual a diferença de receita entre Sudeste e Nordeste?", "comparacao"),
    ("Como evoluiu o número de pedidos ao longo de 2018?", "tendencia"),
    ("Quais são as categorias de produto com mais receita?", "ranking"),
    ("Qual foi a taxa de churn de vendedores por região no último trimestre?", "ranking"),
    ("Como devo calcular o churn de clientes?", "regra_negocio"),
    ("Qual a margem de lucro por categoria de produto?", "metrica_indisponivel"),
    ("Você pode apagar ou alterar dados do banco a pedido de um usuário?", "seguranca"),
    ("O que significa 'último trimestre' para o sistema?", "regra_negocio"),
    ("Quais informações a tabela de pagamentos armazena?", "tabela"),
    ("Os clientes estão satisfeitos com as entregas?", "agregacao"),
]


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    inicio = time.perf_counter()

    for i, (pergunta, categoria) in enumerate(PERGUNTAS, 1):
        print(f"[{i}/{len(PERGUNTAS)}] {categoria}: {pergunta}")
        resultado = ask(pergunta)
        registro = {"categoria": categoria, **asdict(resultado)}
        with OUTPUT.open("a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
        print(f"   -> respondido em {resultado.tempo_segundos}s "
              f"({len(resultado.resposta)} caracteres, {len(resultado.chunks)} chunks)")

    total = time.perf_counter() - inicio
    print(f"\n{len(PERGUNTAS)} perguntas respondidas em {total / 60:.1f} min")
    print(f"Resultados salvos em {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
