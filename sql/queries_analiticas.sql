-- =============================================================================
-- Queries analíticas — Natalidad en México
-- =============================================================================
-- Cinco queries que cubren las técnicas del módulo:
--   1. CTE + ranking        → Top 5 entidades con mayor TGF promedio
--   2. Window function      → Tendencia suavizada de fecundidad (promedio móvil)
--   3. COUNT FILTER         → % de años por entidad sobre tasa de reemplazo
--   4. PERCENTILE_CONT      → Distribución de nacimientos por grupo de edad
--   5. CTE + LAG            → Entidades con mayor caída de fecundidad año a año
-- =============================================================================

SET search_path TO natalidad_dwh;


-- -----------------------------------------------------------------------------
-- 1. Top 5 entidades con mayor Tasa Global de Fecundidad promedio (CTE + ranking)
-- -----------------------------------------------------------------------------

WITH tgf_por_entidad AS (
    SELECT
        de.nombre                                           AS entidad,
        de.region,
        ROUND(SUM(ff.tgf_contribucion), 3)                  AS tgf_total,
        da.año
    FROM      natalidad_dwh.fact_fecundidad  ff
    JOIN      natalidad_dwh.dim_entidad      de USING (entidad_key)
    JOIN      natalidad_dwh.dim_año          da USING (año_key)
    GROUP BY  de.nombre, de.region, da.año
),
promedio_historico AS (
    SELECT
        entidad,
        region,
        ROUND(AVG(tgf_total), 3)    AS tgf_promedio_historico,
        COUNT(*)                    AS años_con_datos
    FROM tgf_por_entidad
    GROUP BY entidad, region
)
SELECT *
FROM      promedio_historico
ORDER BY  tgf_promedio_historico DESC
LIMIT 5;


-- -----------------------------------------------------------------------------
-- 2. Tendencia nacional suavizada de TGF (promedio móvil de 5 años)
-- -----------------------------------------------------------------------------

WITH tgf_nacional_anual AS (
    SELECT
        da.año,
        ROUND(SUM(ff.tgf_contribucion) / COUNT(DISTINCT ff.entidad_key), 4) AS tgf_nacional
    FROM      natalidad_dwh.fact_fecundidad ff
    JOIN      natalidad_dwh.dim_año         da USING (año_key)
    GROUP BY  da.año
)
SELECT
    año,
    tgf_nacional                                                AS tgf_observada,
    ROUND(AVG(tgf_nacional) OVER (
        ORDER BY año
        ROWS BETWEEN 2 PRECEDING AND 2 FOLLOWING
    ), 4)                                                       AS tgf_movil_5años
FROM  tgf_nacional_anual
ORDER BY año;


-- -----------------------------------------------------------------------------
-- 3. % de años en que cada entidad estuvo por encima de la tasa de reemplazo (2.1)
--    usando COUNT FILTER — técnica del módulo
-- -----------------------------------------------------------------------------

WITH tgf_anual AS (
    SELECT
        de.nombre                           AS entidad,
        da.año,
        ROUND(SUM(ff.tgf_contribucion), 3)  AS tgf
    FROM      natalidad_dwh.fact_fecundidad ff
    JOIN      natalidad_dwh.dim_entidad     de USING (entidad_key)
    JOIN      natalidad_dwh.dim_año         da USING (año_key)
    GROUP BY  de.nombre, da.año
)
SELECT
    entidad,
    COUNT(*)                                                AS años_totales,
    COUNT(*) FILTER (WHERE tgf >= 2.1)                     AS años_sobre_reemplazo,
    COUNT(*) FILTER (WHERE tgf < 2.1)                      AS años_bajo_reemplazo,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE tgf >= 2.1) / COUNT(*),
        1
    )                                                       AS pct_sobre_reemplazo
FROM tgf_anual
GROUP BY entidad
ORDER BY pct_sobre_reemplazo DESC;


-- -----------------------------------------------------------------------------
-- 4. Distribución de nacimientos por grupo de edad (mediana + percentil 95)
--    usando PERCENTILE_CONT — función predefinida no trivial
-- -----------------------------------------------------------------------------

SELECT
    dge.rango                                                               AS grupo_edad,
    COUNT(*)                                                                AS observaciones,
    ROUND(AVG(ff.nacimientos), 0)                                           AS promedio,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY ff.nacimientos)            AS mediana,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY ff.nacimientos)            AS percentil_95,
    MIN(ff.nacimientos)                                                     AS minimo,
    MAX(ff.nacimientos)                                                     AS maximo
FROM      natalidad_dwh.fact_fecundidad   ff
JOIN      natalidad_dwh.dim_grupo_edad    dge USING (grupo_edad_key)
WHERE     ff.nacimientos IS NOT NULL
GROUP BY  dge.grupo_edad_key, dge.rango, dge.edad_min
ORDER BY  dge.edad_min;


-- -----------------------------------------------------------------------------
-- 5. Top 10 caídas más bruscas de TGF año a año por entidad (CTE + LAG)
-- -----------------------------------------------------------------------------

WITH tgf_anual AS (
    SELECT
        de.nombre                           AS entidad,
        da.año,
        ROUND(SUM(ff.tgf_contribucion), 3)  AS tgf
    FROM      natalidad_dwh.fact_fecundidad ff
    JOIN      natalidad_dwh.dim_entidad     de USING (entidad_key)
    JOIN      natalidad_dwh.dim_año         da USING (año_key)
    GROUP BY  de.nombre, da.año
)
SELECT
    entidad,
    año,
    tgf                                                             AS tgf_año_actual,
    LAG(tgf) OVER (PARTITION BY entidad ORDER BY año)               AS tgf_año_anterior,
    ROUND(
        tgf - LAG(tgf) OVER (PARTITION BY entidad ORDER BY año),
        4
    )                                                               AS delta_tgf
FROM  tgf_anual
WHERE tgf IS NOT NULL
ORDER BY delta_tgf ASC   -- las caídas más grandes (más negativo = mayor caída)
LIMIT 10;
