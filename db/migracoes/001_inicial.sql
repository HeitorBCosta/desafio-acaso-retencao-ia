-- 001: base analítica do dashboard de retenção (ADR-001).
-- Nenhuma tabela guarda texto de conversa, IP, hash de IP ou user-agent.

CREATE SCHEMA IF NOT EXISTS analytics;

-- Uma linha por usuário (BDR-001), com os fatores da 1ª conversa (BDR-002) e o desfecho (BDR-003).
CREATE TABLE analytics.usuario_primeira_experiencia (
    usuario_id          CHAR(64)    PRIMARY KEY,   -- sha256 de hashed_ip|SO|navegador
    data_chegada        DATE        NOT NULL,      -- 1ª conversa, America/Sao_Paulo
    semana_chegada      DATE        NOT NULL,      -- segunda-feira da semana de chegada
    trimestre           TEXT        NOT NULL,
    modelo              TEXT        NOT NULL,
    turnos_faixa        TEXT        NOT NULL,
    periodo_dia         TEXT        NOT NULL,
    fim_de_semana       TEXT        NOT NULL,
    primeira_mensagem   TEXT        NOT NULL,
    resposta_tamanho    TEXT        NOT NULL,
    recusa              TEXT        NOT NULL,
    recusa_nivel        TEXT        NOT NULL,
    recusa_motivo       TEXT,                      -- só quando houve recusa (BDR-005)
    idioma              TEXT        NOT NULL,
    codigo              TEXT        NOT NULL,
    tema                TEXT,                      -- descritivo; classificação com 67% de acerto
    elegivel            BOOLEAN     NOT NULL,      -- 7 dias observados depois da 1ª conversa
    voltou_7d           BOOLEAN,                   -- NULL quando não elegível
    CHECK (elegivel OR voltou_7d IS NULL),
    CHECK (NOT elegivel OR voltou_7d IS NOT NULL)
);
CREATE INDEX ON analytics.usuario_primeira_experiencia (semana_chegada);
CREATE INDEX ON analytics.usuario_primeira_experiencia (data_chegada);

-- Volume diário de conversas de todos os usuários (detecta dias sem coleta).
CREATE TABLE analytics.conversas_dia (
    dia         DATE    PRIMARY KEY,
    conversas   INTEGER NOT NULL CHECK (conversas >= 0)
);

-- Efeitos pré-calculados na carga (scripts 07, 07b e 09).
CREATE TABLE analytics.efeitos (
    analise             TEXT    NOT NULL,   -- principal | recusa_por_motivo | gpt4_selecao
    fator               TEXT    NOT NULL,
    nivel               TEXT    NOT NULL,
    referencia          TEXT    NOT NULL,
    usuarios            INTEGER NOT NULL,
    voltaram            INTEGER NOT NULL,
    taxa                NUMERIC NOT NULL,
    taxa_referencia     NUMERIC NOT NULL,
    bruto               NUMERIC,
    bruto_ic_baixo      NUMERIC,
    bruto_ic_alto       NUMERIC,
    ajustado            NUMERIC,
    ajustado_ic_baixo   NUMERIC,
    ajustado_ic_alto    NUMERIC,
    metodo              TEXT    NOT NULL,
    aviso               TEXT,
    fonte               TEXT    NOT NULL,
    PRIMARY KEY (analise, fator, nivel)
);

-- Registro de cada carga, para investigar um número depois (seção 4.1).
CREATE TABLE analytics.carga_execucao (
    carga_id            UUID        PRIMARY KEY,
    inicio              TIMESTAMPTZ NOT NULL,
    fim                 TIMESTAMPTZ NOT NULL,
    versao_codigo       TEXT,
    sha256_base_bruta   TEXT        NOT NULL,
    linhas              JSONB       NOT NULL,
    checagens           JSONB       NOT NULL
);
