-- Entregavel 2.1 (E2) - ativa a extensao pgvector assim que o container do
-- banco sobe pela primeira vez. O Docker so roda este arquivo UMA vez, na
-- criacao do volume (docker-entrypoint-initdb.d) - se eu apagar o volume
-- com "docker compose down -v", ele roda de novo do zero.
CREATE EXTENSION IF NOT EXISTS vector;
