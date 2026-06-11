#!/usr/bin/env python3
"""
ETL Pipeline — Natalidad en México (CONAPO/INEGI)

Lee el CSV de indicadores de fecundidad, lo transforma al modelo dimensional
y lo carga a PostgreSQL (local o Aurora).

Uso:
    python etl_pipeline.py \
        --host  localhost \
        --password tu_password \
        --database northwind \
        --csv data/natalidad_mexico.csv

Prerrequisito: las dimensiones ya están pobladas vía los scripts 01-03_*.sql.
"""

import argparse
import logging
import sys

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.types import Integer, Numeric, SmallInteger

logger = logging.getLogger("etl_natalidad")

# Columnas esperadas en el CSV de CONAPO (ajusta según el archivo real)
# Ejemplo de estructura: AÑO, CVE_GEO, ENTIDAD, GRUPO_EDAD, NACIMIENTOS, MUJERES, TASA
COLUMNAS_CSV = {
    "año":          "AÑO",
    "cve_geo":      "CVE_GEO",
    "grupo_edad":   "GRUPO_EDAD",
    "nacimientos":  "NACIMIENTOS",
    "mujeres":      "MUJERES",
    "tasa":         "TASA_ESPECIFICA",
}

TASA_DE_REEMPLAZO = 2.1


# =============================================================================
# Extract
# =============================================================================

def extract(csv_path: str) -> pd.DataFrame:
    """Lee el CSV de natalidad."""
    logger.info("Leyendo CSV: %s", csv_path)
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    logger.info("  %s filas × %s columnas cargadas", *df.shape)
    logger.info("  Columnas: %s", list(df.columns))
    return df


# =============================================================================
# Transform
# =============================================================================

def transform(df: pd.DataFrame) -> pd.DataFrame:
    """Limpia y estandariza el CSV para carga al fact."""
    df = df.copy()

    # Renombrar columnas al esquema interno
    df = df.rename(columns={v: k for k, v in COLUMNAS_CSV.items()})

    # Asegurar tipos
    df["año"]         = pd.to_numeric(df["año"], errors="coerce").astype("Int16")
    df["cve_geo"]     = df["cve_geo"].astype(str).str.zfill(2)
    df["nacimientos"] = pd.to_numeric(df["nacimientos"], errors="coerce").astype("Int32")
    df["mujeres"]     = pd.to_numeric(df["mujeres"],     errors="coerce").astype("Int32")
    df["tasa"]        = pd.to_numeric(df["tasa"],        errors="coerce")

    # Estandarizar grupo_edad al formato "15-19"
    df["grupo_edad"] = df["grupo_edad"].astype(str).str.strip()

    # Calcular contribución al TGF: tasa_especifica * 5 / 1000
    df["tgf_contribucion"] = (df["tasa"] * 5 / 1000).round(6)

    # Eliminar filas sin año o cve_geo
    df = df.dropna(subset=["año", "cve_geo"])

    logger.info("  Después de limpieza: %s filas", len(df))
    return df


def resolve_keys(df: pd.DataFrame, engine) -> pd.DataFrame:
    """Sustituye año, cve_geo y grupo_edad por sus surrogate keys."""
    años = pd.read_sql(
        "SELECT año_key, año FROM natalidad_dwh.dim_año", engine
    )
    entidades = pd.read_sql(
        "SELECT entidad_key, cve_geo FROM natalidad_dwh.dim_entidad", engine
    )
    grupos = pd.read_sql(
        "SELECT grupo_edad_key, rango FROM natalidad_dwh.dim_grupo_edad", engine
    )

    df = df.merge(años,      left_on="año",        right_on="año",    how="inner")
    df = df.merge(entidades, on="cve_geo",                             how="inner")
    df = df.merge(grupos,    left_on="grupo_edad", right_on="rango",   how="inner")

    fact = df[[
        "año_key", "entidad_key", "grupo_edad_key",
        "nacimientos", "mujeres", "tasa", "tgf_contribucion"
    ]].rename(columns={
        "mujeres": "mujeres_en_edad_fertil",
        "tasa":    "tasa_especifica",
    })

    logger.info("  Filas con claves resueltas: %s", len(fact))
    return fact


# =============================================================================
# Load
# =============================================================================

def load(df: pd.DataFrame, engine, chunksize: int = 5000):
    """Carga incrementalmente al fact."""
    logger.info("Cargando %s filas a fact_fecundidad", f"{len(df):,}")

    df.to_sql(
        "fact_fecundidad",
        engine,
        schema="natalidad_dwh",
        if_exists="append",
        index=False,
        method="multi",
        chunksize=chunksize,
        dtype={
            "año_key":                SmallInteger(),
            "entidad_key":            Integer(),
            "grupo_edad_key":         SmallInteger(),
            "nacimientos":            Integer(),
            "mujeres_en_edad_fertil": Integer(),
            "tasa_especifica":        Numeric(8, 4),
            "tgf_contribucion":       Numeric(8, 6),
        },
    )
    logger.info("  Carga completada")


# =============================================================================
# Validate
# =============================================================================

def validate(engine):
    """Validaciones básicas post-carga."""
    logger.info("Ejecutando validaciones post-carga...")

    resumen = pd.read_sql(text("""
        SELECT
            da.año,
            COUNT(DISTINCT ff.entidad_key)          AS entidades,
            SUM(ff.nacimientos)                     AS nacimientos_totales,
            ROUND(AVG(ff.tasa_especifica), 2)       AS tasa_promedio
        FROM      natalidad_dwh.fact_fecundidad ff
        JOIN      natalidad_dwh.dim_año         da USING (año_key)
        GROUP BY  da.año
        ORDER BY  da.año
    """), engine)

    logger.info("Resumen por año:\n%s", resumen.tail(10).to_string(index=False))

    # Sanity: no tasas negativas
    invalidos = pd.read_sql(text("""
        SELECT count(*) AS n FROM natalidad_dwh.fact_fecundidad
        WHERE tasa_especifica < 0
    """), engine).iloc[0, 0]

    assert invalidos == 0, f"Hay {invalidos} tasas negativas — revisar el CSV"
    logger.info("✓ Sin valores inválidos")


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="ETL Natalidad México")
    parser.add_argument("--host",     required=True,  help="Host PostgreSQL o Aurora")
    parser.add_argument("--password", required=True,  help="Contraseña")
    parser.add_argument("--database", default="northwind")
    parser.add_argument("--user",     default="postgres")
    parser.add_argument("--csv",      required=True,  help="Ruta al CSV de natalidad")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    engine = create_engine(
        f"postgresql+psycopg2://{args.user}:{args.password}@{args.host}:5432/{args.database}"
    )

    try:
        df_raw  = extract(args.csv)
        df_clean = transform(df_raw)

        with engine.begin() as conn:
            df_fact = resolve_keys(df_clean, conn)
            load(df_fact, conn)

        validate(engine)
        logger.info("✓ ETL completado correctamente")

    except Exception as exc:
        logger.exception("ETL falló: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
