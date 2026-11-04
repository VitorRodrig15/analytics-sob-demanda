# Entregavel 2.1 (E2) - imagem do container "app", onde rodam todos os
# scripts do projeto (docker compose exec app python scripts/...).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# libpq para o psycopg (conexao com o PostgreSQL); build-essential porque
# algumas dependencias Python compilam extensoes nativas na instalacao.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# So copio o requirements.txt antes do codigo de proposito: assim o Docker
# reaproveita o cache dessa camada e nao reinstala tudo de novo toda vez
# que eu mudo um script - o codigo em si chega via volume (docker-compose.yml).
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Nao tem comando padrao pra rodar aqui (ainda nao existe uma API/servidor
# na E2/E3) - mantenho o container vivo pra usar via "docker compose exec".
CMD ["sleep", "infinity"]
