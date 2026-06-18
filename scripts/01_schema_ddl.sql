-- =============================================================================
-- Proyecto final — Perfil sociodemográfico de madres en México (2010–2018)
-- Alumna: Elizabeth Susana Velázquez Zamora
-- Módulo 4 · Diplomado SQL-NoSQL · IIMAS, UNAM
-- =============================================================================
-- Schema: nacimientos_dwh
-- Grano de la fact: 1 fila por (año × estado × perfil_madre × tipo_parto)
-- Medida principal: total_nacimientos (conteo agregado)
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS nacimientos_dwh;
SET search_path TO nacimientos_dwh;

-- -----------------------------------------------------------------------------
-- DIMENSIONES
-- -----------------------------------------------------------------------------

CREATE TABLE dim_fecha (
    fecha_key       INT         PRIMARY KEY,        -- smart key: YYYY (ej. 2010)
    anio            SMALLINT    NOT NULL UNIQUE,
    decada          VARCHAR(10) NOT NULL,            -- '2010s'
    periodo         VARCHAR(20) NOT NULL            -- 'Primera mitad' / 'Segunda mitad'
);

CREATE TABLE dim_estado (
    estado_key      INT         GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    clave_inegi     SMALLINT    NOT NULL UNIQUE,    -- clave numérica INEGI (01-32)
    nombre_estado   VARCHAR(60) NOT NULL,
    abreviatura     VARCHAR(5)  NOT NULL,
    region          VARCHAR(30) NOT NULL,           -- Norte, Centro, Sur-Sureste
    zona            VARCHAR(20) NOT NULL            -- norte / centro / sur
);

CREATE TABLE dim_madre (
    madre_key       INT         GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    edad_madre      SMALLINT,                       -- edad en años (puede ser nulo si no registrado)
    grupo_edad      VARCHAR(20) NOT NULL,           -- '< 15', '15-19', '20-24', '25-29', '30-34', '35+'
    is_adolescente  BOOLEAN     NOT NULL,           -- TRUE si grupo_edad IN ('< 15', '15-19')
    escolaridad     VARCHAR(40) NOT NULL,           -- 'Sin escolaridad', 'Primaria', 'Secundaria', 'Media superior', 'Superior'
    nivel_escolar   SMALLINT    NOT NULL,           -- orden numérico para ranking: 0-4
    estado_civil    VARCHAR(30) NOT NULL            -- 'Soltera', 'Casada', 'Unión libre', 'Otro'
);

CREATE TABLE dim_tipo_parto (
    tipo_parto_key  INT         GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tipo_parto      VARCHAR(20) NOT NULL,           -- 'Cesárea' / 'Natural / Eutócico'
    institucion     VARCHAR(40) NOT NULL,           -- 'IMSS', 'ISSSTE', 'SSA', 'Privada', 'Otro'
    lugar_parto     VARCHAR(30) NOT NULL            -- 'Hospital', 'Domicilio', 'Otro'
);

-- -----------------------------------------------------------------------------
-- FACT TABLE
-- -----------------------------------------------------------------------------

CREATE TABLE fact_nacimientos (
    nacimiento_id       BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fecha_key           INT         NOT NULL REFERENCES dim_fecha(fecha_key),
    estado_key          INT         NOT NULL REFERENCES dim_estado(estado_key),
    madre_key           INT         NOT NULL REFERENCES dim_madre(madre_key),
    tipo_parto_key      INT         NOT NULL REFERENCES dim_tipo_parto(tipo_parto_key),
    total_nacimientos   INT         NOT NULL DEFAULT 0
);

-- Índices para queries analíticas frecuentes
CREATE INDEX idx_fact_fecha         ON fact_nacimientos(fecha_key);
CREATE INDEX idx_fact_estado        ON fact_nacimientos(estado_key);
CREATE INDEX idx_fact_madre         ON fact_nacimientos(madre_key);
CREATE INDEX idx_fact_estado_fecha  ON fact_nacimientos(estado_key, fecha_key);
CREATE INDEX idx_fact_madre_fecha   ON fact_nacimientos(madre_key, fecha_key);

-- =============================================================================
-- VERIFICACIÓN
-- =============================================================================
-- Listar tablas creadas:
   SELECT table_name
   FROM   information_schema.tables
   WHERE  table_schema = 'nacimientos_dwh';
--
-- Esperado: dim_fecha, dim_estado, dim_madre, dim_tipo_parto, fact_nacimientos
