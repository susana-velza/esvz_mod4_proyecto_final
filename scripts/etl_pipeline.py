#!/usr/bin/env python3
"""
ETL Pipeline — Perfil sociodemográfico de madres en México (2010–2018)

Alumna: Elizabeth Susana Velázquez Zamora
Módulo 4 · Diplomado SQL-NoSQL · IIMAS, UNAM

Lee el CSV de nacimientos descargado de Kaggle (origen INEGI/SINAC),
lo transforma al modelo dimensional y lo carga a Aurora PostgreSQL.

Uso (opción A — variables de entorno desde .env):
    cp .env.example .env        # rellenar con tus datos reales
    export $(cat .env | xargs)
    python scripts/etl_pipeline.py --csv datasets/nacimientos_mexico.csv

Uso (opción B — argumentos explícitos):
    python scripts/etl_pipeline.py \\
        --host     $AURORA_HOST \\
        --password $AURORA_PASSWORD \\
        --database northwind \\
        --csv      datasets/nacimientos_mexico.csv

Prerrequisito: el schema nacimientos_dwh ya existe (ejecutar 01_schema_ddl.sql).
El script es idempotente: hace TRUNCATE de la fact antes de reinsertar.

SEGURIDAD: nunca pongas credenciales directamente en este archivo.
Usa siempre variables de entorno o el archivo .env (que está en .gitignore).
"""

import argparse
import logging
import os
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.types import Integer, SmallInteger, Boolean, String
from tqdm import tqdm

logger = logging.getLogger("etl_nacimientos")

# =============================================================================
# Catálogos de referencia (INEGI)
# =============================================================================

ESTADOS = {
    1:  ("Aguascalientes",   "AGS",  "Centro", "centro"),
    2:  ("Baja California",  "BC",   "Norte",  "norte"),
    3:  ("Baja California Sur", "BCS", "Norte", "norte"),
    4:  ("Campeche",         "CAM",  "Sur-Sureste", "sur"),
    5:  ("Coahuila",         "COAH", "Norte",  "norte"),
    6:  ("Colima",           "COL",  "Centro", "centro"),
    7:  ("Chiapas",          "CHIS", "Sur-Sureste", "sur"),
    8:  ("Chihuahua",        "CHIH", "Norte",  "norte"),
    9:  ("Ciudad de México", "CDMX", "Centro", "centro"),
    10: ("Durango",          "DGO",  "Norte",  "norte"),
    11: ("Guanajuato",       "GTO",  "Centro", "centro"),
    12: ("Guerrero",         "GRO",  "Sur-Sureste", "sur"),
    13: ("Hidalgo",          "HGO",  "Centro", "centro"),
    14: ("Jalisco",          "JAL",  "Centro", "centro"),
    15: ("Estado de México", "MEX",  "Centro", "centro"),
    16: ("Michoacán",        "MICH", "Centro", "centro"),
    17: ("Morelos",          "MOR",  "Centro", "centro"),
    18: ("Nayarit",          "NAY",  "Norte",  "norte"),
    19: ("Nuevo León",       "NL",   "Norte",  "norte"),
    20: ("Oaxaca",           "OAX",  "Sur-Sureste", "sur"),
    21: ("Puebla",           "PUE",  "Centro", "centro"),
    22: ("Querétaro",        "QRO",  "Centro", "centro"),
    23: ("Quintana Roo",     "QROO", "Sur-Sureste", "sur"),
    24: ("San Luis Potosí",  "SLP",  "Centro", "centro"),
    25: ("Sinaloa",          "SIN",  "Norte",  "norte"),
    26: ("Sonora",           "SON",  "Norte",  "norte"),
    27: ("Tabasco",          "TAB",  "Sur-Sureste", "sur"),
    28: ("Tamaulipas",       "TAMS", "Norte",  "norte"),
    29: ("Tlaxcala",         "TLAX", "Centro", "centro"),
    30: ("Veracruz",         "VER",  "Sur-Sureste", "sur"),
    31: ("Yucatán",          "YUC",  "Sur-Sureste", "sur"),
    32: ("Zacatecas",        "ZAC",  "Centro", "centro"),
}

GRUPOS_EDAD = [
    ("< 15",  True,  0, 14),
    ("15-19", True,  15, 19),
    ("20-24", False, 20, 24),
    ("25-29", False, 25, 29),
    ("30-34", False, 30, 34),
    ("35+",   False, 35, 99),
]

ESCOLARIDAD_MAP = {
    "sin escolaridad":  (0, "Sin escolaridad"),
    "primaria":         (1, "Primaria"),
    "secundaria":       (2, "Secundaria"),
    "media superior":   (3, "Media superior"),
    "superior":         (4, "Superior"),
    "no especificado":  (2, "Secundaria"),   # imputación conservadora
}


# =============================================================================
# Extract
# =============================================================================

def extract(csv_path: str) -> pd.DataFrame:
    """Lee el CSV de Kaggle y realiza validaciones básicas de estructura."""
    logger.info("Leyendo CSV: %s", csv_path)
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    logger.info("  Shape original: %s filas × %s columnas", *df.shape)

    # Normalizar nombres de columna
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace("á", "a").str.replace("é", "e")
        .str.replace("í", "i").str.replace("ó", "o")
        .str.replace("ú", "u").str.replace("ñ", "n")
    )
    logger.info("  Columnas: %s", list(df.columns))
    return df


# =============================================================================
# Transform
# =============================================================================

def _asignar_grupo_edad(edad: float) -> tuple[str, bool]:
    """Devuelve (grupo_edad, is_adolescente) para una edad en años."""
    if pd.isna(edad):
        return ("No especificado", False)
    for grupo, es_adol, min_e, max_e in GRUPOS_EDAD:
        if min_e <= int(edad) <= max_e:
            return (grupo, es_adol)
    return ("35+", False)


def transform_dim_fecha(df: pd.DataFrame) -> pd.DataFrame:
    """Construye dim_fecha a partir de los años únicos del dataset."""
    anios = sorted(df["anio"].dropna().unique().astype(int))
    rows = []
    for a in anios:
        rows.append({
            "fecha_key": a,
            "anio":      a,
            "decada":    f"{(a // 10) * 10}s",
            "periodo":   "Primera mitad (2010-2014)" if a <= 2014 else "Segunda mitad (2015-2018)",
        })
    return pd.DataFrame(rows)


def transform_dim_estado(df: pd.DataFrame) -> pd.DataFrame:
    """Construye dim_estado a partir de los estados únicos del CSV."""
    estados_csv = df["estado"].dropna().unique()
    rows = []
    for nombre in sorted(estados_csv):
        # Buscar en catálogo INEGI por nombre
        match = next(
            ((r, z) for _, (n, _, r, z) in ESTADOS.items() if n == nombre),
            ("Centro", "centro")
        )
        rows.append({
            "nombre_estado": nombre,
            "region":        match[0],
            "zona":          match[1],
        })
    return pd.DataFrame(rows)


def transform_dim_madre(df: pd.DataFrame) -> pd.DataFrame:
    """
    Construye dim_madre con todas las combinaciones únicas de
    (grupo_edad, escolaridad, estado_civil).
    El CSV ya trae grupo_edad, is_adolescente y nivel_escolar precalculados.
    """
    col_grupo = _detectar_columna(df, ["grupo_edad"])
    col_adol  = _detectar_columna(df, ["is_adolescente"])
    col_esc   = _detectar_columna(df, ["escolaridad", "nivel_escolaridad"])
    col_nivel = _detectar_columna(df, ["nivel_escolar"], requerida=False)
    col_civil = _detectar_columna(df, ["estado_civil", "civil"])

    combos = (
        df[[col_grupo, col_adol, col_esc, col_civil]]
        .drop_duplicates()
        .reset_index(drop=True)
    )

    rows = []
    for _, row in combos.iterrows():
        grupo   = str(row[col_grupo]).strip()
        is_adol = str(row[col_adol]).lower() in ("true", "1", "yes")
        esc_raw = str(row[col_esc]).strip().lower()
        nivel, esc_label = ESCOLARIDAD_MAP.get(esc_raw, (2, str(row[col_esc]).strip()))
        civil   = str(row[col_civil]).strip().capitalize()

        rows.append({
            "edad_madre":     None,
            "grupo_edad":     grupo,
            "is_adolescente": is_adol,
            "escolaridad":    esc_label,
            "nivel_escolar":  nivel,
            "estado_civil":   civil,
            "_esc_raw":       esc_raw,
        })

    dim = pd.DataFrame(rows).drop_duplicates(
        subset=["grupo_edad", "escolaridad", "estado_civil"]
    ).reset_index(drop=True)
    logger.info("  dim_madre: %s combinaciones únicas", len(dim))
    return dim


def transform_dim_tipo_parto(df: pd.DataFrame) -> pd.DataFrame:
    """Construye dim_tipo_parto con las combinaciones únicas disponibles."""
    col_tipo = _detectar_columna(df, ["tipo_parto", "parto", "tipo_de_parto"])
    col_inst = _detectar_columna(df, ["institucion", "institucion_salud", "inst_salud"], requerida=False)
    col_lugar = _detectar_columna(df, ["lugar_parto", "lugar", "lugar_de_parto"], requerida=False)

    cols = [col_tipo]
    if col_inst:
        cols.append(col_inst)
    if col_lugar:
        cols.append(col_lugar)

    combos = df[cols].drop_duplicates().reset_index(drop=True)
    rows = []
    for _, row in combos.iterrows():
        tipo = str(row[col_tipo]).strip().capitalize() if pd.notna(row[col_tipo]) else "No especificado"
        inst  = str(row[col_inst]).strip()  if col_inst  and pd.notna(row.get(col_inst))  else "No especificado"
        lugar = str(row[col_lugar]).strip() if col_lugar and pd.notna(row.get(col_lugar)) else "Hospital"
        rows.append({
            "tipo_parto": tipo,
            "institucion": inst,
            "lugar_parto": lugar,
            "_tipo_raw":  tipo,
            "_inst_raw":  inst,
        })
    return pd.DataFrame(rows).drop_duplicates(
        subset=["tipo_parto", "institucion", "lugar_parto"]
    ).reset_index(drop=True)


def _detectar_columna(df: pd.DataFrame, candidatos: list, requerida: bool = True) -> str | None:
    """Busca la primera columna candidata presente en el DataFrame."""
    for c in candidatos:
        if c in df.columns:
            return c
    if requerida:
        raise ValueError(
            f"No se encontró ninguna de las columnas {candidatos} en el CSV. "
            f"Columnas disponibles: {list(df.columns)}"
        )
    return None


def resolve_keys_and_build_fact(
    df: pd.DataFrame,
    dim_fecha: pd.DataFrame,
    dim_estado: pd.DataFrame,
    dim_madre: pd.DataFrame,
    dim_tipo_parto: pd.DataFrame,
) -> pd.DataFrame:
    """
    Construye la fact table resolviendo surrogate keys
    y agregando total_nacimientos.
    """
    col_anio  = _detectar_columna(df, ["anio", "año", "year"])
    col_estado = _detectar_columna(df, ["estado", "nombre_estado"])
    col_grupo = _detectar_columna(df, ["grupo_edad"])
    col_esc   = _detectar_columna(df, ["escolaridad", "nivel_escolaridad"])
    col_civil = _detectar_columna(df, ["estado_civil", "civil"])
    col_tipo  = _detectar_columna(df, ["tipo_parto", "parto", "tipo_de_parto"])
    col_nac   = _detectar_columna(df, ["total_nacimientos", "nacimientos", "total", "count"])

    fact = df[[col_anio, col_estado, col_grupo, col_esc, col_civil, col_tipo, col_nac]].copy()
    fact.columns = ["anio", "nombre_estado", "grupo_edad", "esc_raw", "estado_civil", "tipo_raw", "total_nacimientos"]

    def _esc_label(e):
        raw = str(e).strip().lower() if pd.notna(e) else "no especificado"
        _, label = ESCOLARIDAD_MAP.get(raw, (2, str(e).strip()))
        return label

    fact["escolaridad"] = fact["esc_raw"].apply(_esc_label)
    fact["estado_civil"] = fact["estado_civil"].apply(lambda x: str(x).strip().capitalize() if pd.notna(x) else "No especificado")
    fact["tipo_parto"]   = fact["tipo_raw"].apply(lambda x: str(x).strip() if pd.notna(x) else "No especificado")

    # Merge con dim_fecha
    fact = fact.merge(
        dim_fecha[["fecha_key", "anio"]],
        on="anio", how="left", validate="many_to_one"
    )

    # Merge con dim_estado por nombre
    dim_estado_merge = dim_estado[["estado_key", "nombre_estado"]]
    fact = fact.merge(dim_estado_merge, on="nombre_estado", how="left", validate="many_to_one")

    # Merge con dim_madre
    dim_madre_merge = dim_madre[["madre_key", "grupo_edad", "escolaridad", "estado_civil"]]
    fact = fact.merge(dim_madre_merge, on=["grupo_edad", "escolaridad", "estado_civil"], how="left", validate="many_to_one")

    # Merge con dim_tipo_parto
    dim_tipo_merge = dim_tipo_parto[["tipo_parto_key", "tipo_parto"]].drop_duplicates(subset=["tipo_parto"])
    fact = fact.merge(dim_tipo_merge, on="tipo_parto", how="left")

    # Seleccionar columnas finales y agregar
    fact_final = (
        fact[["fecha_key", "estado_key", "madre_key", "tipo_parto_key", "total_nacimientos"]]
        .dropna(subset=["fecha_key", "estado_key", "madre_key", "tipo_parto_key"])
        .groupby(["fecha_key", "estado_key", "madre_key", "tipo_parto_key"], as_index=False)
        ["total_nacimientos"].sum()
    )
    fact_final = fact_final.astype({
        "fecha_key":      int,
        "estado_key":     int,
        "madre_key":      int,
        "tipo_parto_key": int,
        "total_nacimientos": int,
    })
    logger.info("  fact_nacimientos: %s filas a cargar", f"{len(fact_final):,}")
    return fact_final


# =============================================================================
# Load
# =============================================================================

def load_dimension(df: pd.DataFrame, table: str, engine, pk_col: str = None):
    """Carga una dimensión con TRUNCATE + INSERT (idempotente)."""
    schema = "nacimientos_dwh"
    logger.info("Cargando %s (%s filas)", table, len(df))

    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE {schema}.{table} RESTART IDENTITY CASCADE"))

    cols = [c for c in df.columns if not c.startswith("_") and c not in ("estado_key", "madre_key", "tipo_parto_key")]
    df[cols].to_sql(
        table, engine, schema=schema,
        if_exists="append", index=False, method="multi"
    )


def load_fact(df: pd.DataFrame, engine, chunksize: int = 5000):
    """Carga la fact con TRUNCATE + INSERT en chunks."""
    schema = "nacimientos_dwh"
    logger.info("Cargando fact_nacimientos (%s filas)", f"{len(df):,}")

    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE {schema}.fact_nacimientos RESTART IDENTITY"))

    n_chunks = (len(df) + chunksize - 1) // chunksize
    for i in tqdm(range(n_chunks), desc="  cargando fact"):
        chunk = df.iloc[i * chunksize:(i + 1) * chunksize]
        chunk.to_sql(
            "fact_nacimientos", engine, schema=schema,
            if_exists="append", index=False, method="multi",
            dtype={
                "fecha_key":          Integer(),
                "estado_key":         Integer(),
                "madre_key":          Integer(),
                "tipo_parto_key":     Integer(),
                "total_nacimientos":  Integer(),
            },
        )


# =============================================================================
# Validate
# =============================================================================

def validate(engine):
    """Validaciones post-carga: conteos, integridad referencial, sanity checks."""
    logger.info("Ejecutando validaciones post-carga...")

    with engine.connect() as conn:
        # Conteo general
        resumen = pd.read_sql(text("""
            SELECT
                dd.anio,
                SUM(fn.total_nacimientos)  AS nacimientos_totales,
                COUNT(DISTINCT fn.estado_key) AS estados_cubiertos,
                COUNT(DISTINCT fn.madre_key)  AS perfiles_madre
            FROM   nacimientos_dwh.fact_nacimientos fn
            JOIN   nacimientos_dwh.dim_fecha dd USING (fecha_key)
            GROUP BY dd.anio
            ORDER BY dd.anio
        """), conn)
        logger.info("Resumen por año:\n%s", resumen.to_string(index=False))

        # Sin NULLs en FKs
        nulls = pd.read_sql(text("""
            SELECT COUNT(*) AS n
            FROM   nacimientos_dwh.fact_nacimientos
            WHERE  fecha_key IS NULL
               OR  estado_key IS NULL
               OR  madre_key IS NULL
               OR  tipo_parto_key IS NULL
        """), conn).iloc[0, 0]
        assert nulls == 0, f"Hay {nulls} filas con FKs nulas — revisar el ETL"
        logger.info("✓ Sin FKs nulas")

        # Sin valores negativos
        negativos = pd.read_sql(text("""
            SELECT COUNT(*) AS n
            FROM   nacimientos_dwh.fact_nacimientos
            WHERE  total_nacimientos < 0
        """), conn).iloc[0, 0]
        assert negativos == 0, f"Hay {negativos} filas con total_nacimientos < 0"
        logger.info("✓ Sin valores negativos en total_nacimientos")

        # Cobertura de estados (deben ser 32)
        n_estados = pd.read_sql(text("""
            SELECT COUNT(DISTINCT estado_key) AS n
            FROM   nacimientos_dwh.fact_nacimientos
        """), conn).iloc[0, 0]
        if n_estados < 32:
            logger.warning("Solo %s de 32 estados tienen registros — revisar CSV", n_estados)
        else:
            logger.info("✓ Los 32 estados tienen registros")

    logger.info("✓ Validaciones completadas")


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="ETL — Nacimientos México (INEGI 2010-2018)"
    )
    # Las credenciales se leen primero desde variables de entorno;
    # los argumentos CLI las sobreescriben si se pasan explícitamente.
    parser.add_argument(
        "--host",
        default=os.environ.get("AURORA_HOST", ""),
        help="Host de Aurora (o variable de entorno AURORA_HOST)",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("AURORA_PASSWORD", ""),
        help="Contraseña de Aurora (o variable de entorno AURORA_PASSWORD)",
    )
    parser.add_argument(
        "--database",
        default=os.environ.get("AURORA_DATABASE", "northwind"),
        help="Nombre de la base de datos (o variable de entorno AURORA_DATABASE)",
    )
    parser.add_argument("--csv", required=True, help="Ruta al CSV de Kaggle")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # Validar que las credenciales estén presentes
    if not args.host:
        logger.error(
            "Falta AURORA_HOST. Defínelo en .env o pasa --host como argumento."
        )
        sys.exit(1)
    if not args.password:
        logger.error(
            "Falta AURORA_PASSWORD. Defínelo en .env o pasa --password como argumento."
        )
        sys.exit(1)

    if not Path(args.csv).exists():
        logger.error("No se encontró el archivo CSV: %s", args.csv)
        sys.exit(1)

    # La URL de conexión nunca se imprime en logs para evitar exponer credenciales
    logger.info("Conectando a Aurora: %s / %s", args.host, args.database)
    engine = create_engine(
        f"postgresql+psycopg2://postgres:{args.password}@{args.host}:5432/{args.database}"
    )

    try:
        # ----- Extract -----
        df_raw = extract(args.csv)

        # ----- Transform -----
        logger.info("Transformando dimensiones...")
        dim_fecha      = transform_dim_fecha(df_raw)
        dim_estado     = transform_dim_estado(df_raw)
        dim_madre      = transform_dim_madre(df_raw)
        dim_tipo_parto = transform_dim_tipo_parto(df_raw)

        # Agregar surrogate keys a las dimensiones antes del merge
        dim_estado["estado_key"]         = range(1, len(dim_estado) + 1)
        dim_madre["madre_key"]           = range(1, len(dim_madre) + 1)
        dim_tipo_parto["tipo_parto_key"] = range(1, len(dim_tipo_parto) + 1)

        logger.info("Construyendo fact table...")
        fact = resolve_keys_and_build_fact(
            df_raw, dim_fecha, dim_estado, dim_madre, dim_tipo_parto
        )

        # ----- Load -----
        logger.info("Cargando a Aurora...")
        load_dimension(dim_fecha,      "dim_fecha",      engine)
        load_dimension(dim_estado,     "dim_estado",     engine)
        load_dimension(dim_madre,      "dim_madre",      engine)
        load_dimension(dim_tipo_parto, "dim_tipo_parto", engine)
        load_fact(fact, engine)

        # ----- Validate -----
        validate(engine)

        logger.info("ETL completado exitosamente ✓")

    except Exception as exc:
        logger.exception("ETL falló: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
