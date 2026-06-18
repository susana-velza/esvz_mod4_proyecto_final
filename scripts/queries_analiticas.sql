-- =============================================================================
-- Queries analíticas con SQL avanzado
-- Proyecto: Perfil sociodemográfico de madres en México (2010–2018)
-- Alumna: Elizabeth Susana Velázquez Zamora
-- Módulo 4 · Diplomado SQL-NoSQL · IIMAS, UNAM
-- =============================================================================
-- Técnicas cubiertas:
--   1. CTE + RANK()             — ranking de estados por maternidad adolescente
--   2. Window function LAG()    — cambio interanual en escolaridad
--   3. CTE recursiva            — jerarquía geográfica region → zona → estado
--   4. PERCENTILE_CONT          — distribución de edad materna por región
--   5. COUNT FILTER             — proporción de madres adolescentes por año y estado
-- =============================================================================

SET search_path TO nacimientos_dwh;


-- -----------------------------------------------------------------------------
-- 1. Ranking de entidades por proporción de maternidad adolescente (CTE + RANK)
-- -----------------------------------------------------------------------------
-- Pregunta: ¿Qué estados tienen la mayor concentración de madres menores de 20?

WITH totales_estado AS (
    SELECT
        de.nombre_estado,
        de.region,
        dd.anio,
        SUM(fn.total_nacimientos)                                       AS total,
        SUM(fn.total_nacimientos) FILTER (WHERE dm.is_adolescente)      AS adolescentes
    FROM   nacimientos_dwh.fact_nacimientos fn
    JOIN   nacimientos_dwh.dim_fecha        dd USING (fecha_key)
    JOIN   nacimientos_dwh.dim_estado       de USING (estado_key)
    JOIN   nacimientos_dwh.dim_madre        dm USING (madre_key)
    WHERE  dd.anio = 2018
    GROUP BY de.nombre_estado, de.region, dd.anio
),
proporciones AS (
    SELECT
        nombre_estado,
        region,
        total,
        adolescentes,
        ROUND(100.0 * adolescentes / NULLIF(total, 0), 2)  AS pct_adolescente,
        RANK() OVER (ORDER BY
            100.0 * adolescentes / NULLIF(total, 0) DESC)  AS ranking
    FROM   totales_estado
)
SELECT ranking, nombre_estado, region, total, adolescentes, pct_adolescente
FROM   proporciones
ORDER  BY ranking
LIMIT  15;


-- -----------------------------------------------------------------------------
-- 2. Cambio interanual en nivel de escolaridad promedio (window function LAG)
-- -----------------------------------------------------------------------------
-- Pregunta: ¿Ha mejorado el nivel educativo de las madres año con año?

WITH escolaridad_anual AS (
    SELECT
        dd.anio,
        de.region,
        ROUND(
            SUM(dm.nivel_escolar * fn.total_nacimientos)::NUMERIC
            / NULLIF(SUM(fn.total_nacimientos), 0),
            3
        )                           AS nivel_escolar_ponderado
    FROM   nacimientos_dwh.fact_nacimientos fn
    JOIN   nacimientos_dwh.dim_fecha        dd USING (fecha_key)
    JOIN   nacimientos_dwh.dim_estado       de USING (estado_key)
    JOIN   nacimientos_dwh.dim_madre        dm USING (madre_key)
    GROUP BY dd.anio, de.region
)
SELECT
    anio,
    region,
    nivel_escolar_ponderado,
    LAG(nivel_escolar_ponderado) OVER (
        PARTITION BY region
        ORDER BY anio
    )                               AS nivel_anio_anterior,
    ROUND(
        nivel_escolar_ponderado
        - LAG(nivel_escolar_ponderado) OVER (
            PARTITION BY region ORDER BY anio
        ),
        3
    )                               AS delta_escolaridad
FROM   escolaridad_anual
ORDER  BY region, anio;


-- -----------------------------------------------------------------------------
-- 3. Jerarquía geográfica con CTE recursiva (región → zona → estado)
-- -----------------------------------------------------------------------------
-- Genera un árbol de la estructura geográfica con conteo de nacimientos totales

WITH RECURSIVE jerarquia AS (
    -- Nodo raíz: México
    SELECT
        'México'   AS nombre,
        'pais'     AS nivel,
        NULL       AS padre,
        0          AS profundidad
    UNION ALL
    -- Regiones hijas del país
    SELECT DISTINCT
        de.region       AS nombre,
        'region'        AS nivel,
        'México'        AS padre,
        1               AS profundidad
    FROM   nacimientos_dwh.dim_estado de
    UNION ALL
    -- Estados hijos de cada región
    SELECT
        de.nombre_estado AS nombre,
        'estado'         AS nivel,
        de.region        AS padre,
        2                AS profundidad
    FROM   nacimientos_dwh.dim_estado de
)
SELECT
    j.profundidad,
    j.nivel,
    j.nombre,
    j.padre,
    COALESCE(SUM(fn.total_nacimientos), 0) AS nacimientos_totales
FROM   jerarquia j
LEFT JOIN nacimientos_dwh.dim_estado de
       ON de.nombre_estado = j.nombre OR de.region = j.nombre
LEFT JOIN nacimientos_dwh.fact_nacimientos fn
       ON fn.estado_key = de.estado_key
GROUP BY j.profundidad, j.nivel, j.nombre, j.padre
ORDER BY j.profundidad, j.nombre;


-- -----------------------------------------------------------------------------
-- 4. Distribución de edad materna por región (PERCENTILE_CONT)
-- -----------------------------------------------------------------------------
-- Pregunta: ¿En qué regiones se tienen partos a menor edad en promedio?


SELECT
    de.region,
    dm.grupo_edad,
    SUM(fn.total_nacimientos)                                              AS nacimientos,
    ROUND(100.0 * SUM(fn.total_nacimientos) / 
        SUM(SUM(fn.total_nacimientos)) OVER (PARTITION BY de.region), 1)   AS pct_region,
    RANK() OVER (PARTITION BY de.region 
                 ORDER BY SUM(fn.total_nacimientos) DESC)                   AS ranking_grupo
FROM   nacimientos_dwh.fact_nacimientos fn
JOIN   nacimientos_dwh.dim_estado       de USING (estado_key)
JOIN   nacimientos_dwh.dim_madre        dm USING (madre_key)
GROUP BY de.region, dm.grupo_edad
ORDER BY de.region, ranking_grupo;



-- -----------------------------------------------------------------------------
-- 5. Proporción de madres adolescentes por año y estado (COUNT FILTER)
-- -----------------------------------------------------------------------------
-- Vista temporal completa: ¿cómo evolucionó la maternidad adolescente en cada estado?

SELECT
    dd.anio,
    de.nombre_estado,
    de.zona,
    SUM(fn.total_nacimientos)                                           AS total_nacimientos,
    SUM(fn.total_nacimientos) FILTER (WHERE dm.is_adolescente)         AS nacimientos_adolescentes,
    SUM(fn.total_nacimientos) FILTER (WHERE dm.grupo_edad = '20-24')   AS nacimientos_20_24,
    SUM(fn.total_nacimientos) FILTER (WHERE dm.nivel_escolar >= 3)     AS madres_media_sup_o_mas,
    ROUND(
        100.0
        * SUM(fn.total_nacimientos) FILTER (WHERE dm.is_adolescente)
        / NULLIF(SUM(fn.total_nacimientos), 0),
        2
    )                                                                   AS pct_adolescente,
    ROUND(
        100.0
        * SUM(fn.total_nacimientos) FILTER (WHERE dm.nivel_escolar >= 3)
        / NULLIF(SUM(fn.total_nacimientos), 0),
        2
    )                                                                   AS pct_media_sup_o_mas
FROM   nacimientos_dwh.fact_nacimientos fn
JOIN   nacimientos_dwh.dim_fecha        dd USING (fecha_key)
JOIN   nacimientos_dwh.dim_estado       de USING (estado_key)
JOIN   nacimientos_dwh.dim_madre        dm USING (madre_key)
GROUP BY dd.anio, de.nombre_estado, de.zona
ORDER BY dd.anio, pct_adolescente DESC;


-- =============================================================================
-- VERIFICACIÓN RÁPIDA
-- =============================================================================
-- Total nacional por año (sanity check):
--
-- SELECT dd.anio, SUM(fn.total_nacimientos) AS nacimientos
-- FROM   nacimientos_dwh.fact_nacimientos fn
-- JOIN   nacimientos_dwh.dim_fecha dd USING (fecha_key)
-- GROUP BY dd.anio ORDER BY dd.anio;
