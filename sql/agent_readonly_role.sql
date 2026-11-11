-- =============================================================================
-- Entregável 4.3 (E4) - Usuário somente leitura para a ferramenta consulta_banco
--
-- A partir da E4, pela primeira vez, uma SQL gerada pelo agente vai rodar de
-- verdade contra o schema dw. Até aqui (E3) o agente só explicava o
-- dicionário - nunca tocava no banco. Por isso crio este papel ANTES de
-- escrever a ferramenta: mesmo que o agente "decida" tentar algo além de um
-- SELECT, ou que uma pergunta maliciosa tente induzir isso, é o próprio
-- PostgreSQL quem recusa - não dependo de o modelo obedecer uma instrução.
--
-- Idempotente: pode rodar várias vezes sem erro.
-- Executar como script no DBeaver (Alt + X), conectado como "analytics".
-- =============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'agente_leitura') THEN
        CREATE ROLE agente_leitura LOGIN PASSWORD 'troque_esta_senha_no_env';
    END IF;
END
$$;

-- Só enxerga o schema dw (dados de negócio) - nem precisa saber que o
-- schema rag existe, já que a busca vetorial é feita pela ferramenta
-- busca_vetorial, com a conexão normal, não por esta role.
GRANT CONNECT ON DATABASE analytics TO agente_leitura;
GRANT USAGE ON SCHEMA dw TO agente_leitura;
GRANT SELECT ON ALL TABLES IN SCHEMA dw TO agente_leitura;

-- Tabelas criadas depois desta role também ficam com SELECT liberado
-- automaticamente, sem eu precisar lembrar de rodar o GRANT de novo.
ALTER DEFAULT PRIVILEGES FOR ROLE analytics IN SCHEMA dw
    GRANT SELECT ON TABLES TO agente_leitura;

-- As duas travas que realmente importam: toda sessão desta role já nasce
-- em modo somente leitura (INSERT/UPDATE/DELETE são recusados pelo próprio
-- Postgres, não por uma regra de aplicação), e nenhuma consulta pode travar
-- o banco por mais de 30 segundos.
ALTER ROLE agente_leitura SET default_transaction_read_only = on;
ALTER ROLE agente_leitura SET statement_timeout = '30s';

COMMENT ON ROLE agente_leitura IS
    'Usado pela ferramenta consulta_banco do agente (E4). Só SELECT no schema dw, transação sempre read-only, timeout de 30s.';
