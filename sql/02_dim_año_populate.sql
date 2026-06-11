-- =============================================================================
-- Poblar dim_año (1990–2023) y dim_grupo_edad (7 grupos estándar CONAPO)
-- =============================================================================

SET search_path TO natalidad_dwh;

-- -----------------------------------------------------------------------------
-- dim_año
-- -----------------------------------------------------------------------------

INSERT INTO dim_año (año_key, año, decada, periodo)
SELECT
    y                           AS año_key,
    y                           AS año,
    (y / 10) * 10               AS decada,
    CASE
        WHEN y BETWEEN 1990 AND 1999 THEN 'Transición temprana'
        WHEN y BETWEEN 2000 AND 2009 THEN 'Transición media'
        WHEN y BETWEEN 2010 AND 2019 THEN 'Transición avanzada'
        ELSE 'Post-transición'
    END                         AS periodo
FROM generate_series(1990, 2023) AS y;

-- -----------------------------------------------------------------------------
-- dim_grupo_edad (grupos quinquenales de edad fértil)
-- -----------------------------------------------------------------------------

INSERT INTO dim_grupo_edad (grupo_edad_key, rango, edad_min, edad_max) VALUES
    (1, '15-19', 15, 19),
    (2, '20-24', 20, 24),
    (3, '25-29', 25, 29),
    (4, '30-34', 30, 34),
    (5, '35-39', 35, 39),
    (6, '40-44', 40, 44),
    (7, '45-49', 45, 49);

-- =============================================================================
-- VERIFICACIÓN
-- =============================================================================
-- SELECT count(*) FROM natalidad_dwh.dim_año;        -- esperado: 34
-- SELECT * FROM natalidad_dwh.dim_año ORDER BY año;
-- SELECT * FROM natalidad_dwh.dim_grupo_edad;        -- esperado: 7 filas
