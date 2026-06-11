-- =============================================================================
-- Proyecto Final — Natalidad en México
-- =============================================================================
-- Schema: natalidad_dwh
-- Grano de la fact: una fila por (año × entidad_federativa × grupo_edad)
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS natalidad_dwh;
SET search_path TO natalidad_dwh;

-- -----------------------------------------------------------------------------
-- DIMENSIONES
-- -----------------------------------------------------------------------------

CREATE TABLE dim_año (
    año_key         SMALLINT    PRIMARY KEY,   -- el mismo año como clave (1990-2023)
    año             SMALLINT    NOT NULL UNIQUE,
    decada          SMALLINT    NOT NULL,       -- 1990, 2000, 2010, 2020
    periodo         VARCHAR(20) NOT NULL        -- "Transición temprana", "Transición avanzada", etc.
);

CREATE TABLE dim_entidad (
    entidad_key     INT         GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cve_geo         CHAR(2)     NOT NULL UNIQUE,  -- clave INEGI (01=AGS, 09=CDMX, etc.)
    nombre          VARCHAR(60) NOT NULL,
    region          VARCHAR(30) NOT NULL,          -- Norte, Centro, Sur-Sureste
    tipo_zona       VARCHAR(20) NOT NULL           -- Urbana alta, Urbana media, Rural
);

CREATE TABLE dim_grupo_edad (
    grupo_edad_key  SMALLINT    PRIMARY KEY,
    rango           VARCHAR(10) NOT NULL UNIQUE,   -- "15-19", "20-24", ... "45-49"
    edad_min        SMALLINT    NOT NULL,
    edad_max        SMALLINT    NOT NULL
);

-- -----------------------------------------------------------------------------
-- FACT
-- -----------------------------------------------------------------------------

CREATE TABLE fact_fecundidad (
    fecundidad_id           BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    año_key                 SMALLINT    NOT NULL REFERENCES dim_año(año_key),
    entidad_key             INT         NOT NULL REFERENCES dim_entidad(entidad_key),
    grupo_edad_key          SMALLINT    NOT NULL REFERENCES dim_grupo_edad(grupo_edad_key),
    nacimientos             INT,                   -- número de nacimientos registrados
    mujeres_en_edad_fertil  INT,                   -- población femenina en ese rango de edad
    tasa_especifica         NUMERIC(8,4),           -- nacimientos / mujeres * 1000
    tgf_contribucion        NUMERIC(8,6)            -- aporte al TGF total (tasa_especifica * 5 / 1000)
);

-- Índices para queries analíticas
CREATE INDEX idx_fact_año_entidad   ON fact_fecundidad(año_key, entidad_key);
CREATE INDEX idx_fact_entidad       ON fact_fecundidad(entidad_key);
CREATE INDEX idx_fact_grupo_edad    ON fact_fecundidad(grupo_edad_key);

-- =============================================================================
-- VERIFICACIÓN
-- =============================================================================
-- SELECT table_name FROM information_schema.tables WHERE table_schema = 'natalidad_dwh';
-- Esperado: dim_año, dim_entidad, dim_grupo_edad, fact_fecundidad
