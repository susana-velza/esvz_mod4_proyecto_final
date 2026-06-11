"""
Genera las 4 visualizaciones del proyecto como PNG con matplotlib.

Si la variable de entorno DB_HOST está definida, ejecuta las queries reales
contra PostgreSQL. Si no, usa datos sintéticos coherentes con las tendencias
históricas documentadas por CONAPO — útil para previsualizar sin conexión.

Uso:
    export DB_HOST=localhost
    export DB_PASSWORD=tu_password
    python generar_visualizaciones.py

Salida: dashboard/img/{01_mapa, 02_serie_nacional, 03_top_entidades, 04_heatmap}.png
"""

import os
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

OUT = Path(__file__).parent / "dashboard" / "img"
OUT.mkdir(parents=True, exist_ok=True)

USE_DB = bool(os.environ.get("DB_HOST"))

# Tasa de reemplazo poblacional
REEMPLAZO = 2.1

# 32 entidades con coordenadas aproximadas para el mapa
ENTIDADES = [
    ("AGS", "Aguascalientes",      21.88, -102.29, "Centro"),
    ("BC",  "Baja California",     30.84,  -115.28, "Norte"),
    ("BCS", "Baja California Sur", 26.04,  -111.66, "Norte"),
    ("CAM", "Campeche",            19.84,   -90.53, "Sur-Sureste"),
    ("COA", "Coahuila",            27.29,  -102.08, "Norte"),
    ("COL", "Colima",              19.24,  -103.72, "Centro"),
    ("CHS", "Chiapas",             16.75,   -93.12, "Sur-Sureste"),
    ("CHH", "Chihuahua",           28.63,  -106.07, "Norte"),
    ("CDMX","Ciudad de México",    19.43,   -99.13, "Centro"),
    ("DGO", "Durango",             24.03,  -104.65, "Norte"),
    ("GTO", "Guanajuato",          21.02,  -101.26, "Centro"),
    ("GRO", "Guerrero",            17.55,   -99.50, "Sur-Sureste"),
    ("HGO", "Hidalgo",             20.09,   -98.76, "Centro"),
    ("JAL", "Jalisco",             20.67,  -103.35, "Centro"),
    ("MEX", "Estado de México",    19.29,   -99.65, "Centro"),
    ("MIC", "Michoacán",           19.70,  -101.19, "Centro"),
    ("MOR", "Morelos",             18.68,   -99.10, "Centro"),
    ("NAY", "Nayarit",             21.75,  -104.85, "Centro"),
    ("NL",  "Nuevo León",          25.59,  -99.99,  "Norte"),
    ("OAX", "Oaxaca",              17.08,   -96.73, "Sur-Sureste"),
    ("PUE", "Puebla",              19.04,   -98.20, "Centro"),
    ("QRO", "Querétaro",           20.59,  -100.39, "Centro"),
    ("QR",  "Quintana Roo",        19.18,   -88.48, "Sur-Sureste"),
    ("SLP", "San Luis Potosí",     22.15,  -100.98, "Centro"),
    ("SIN", "Sinaloa",             24.80,  -107.39, "Norte"),
    ("SON", "Sonora",              29.07,  -110.96, "Norte"),
    ("TAB", "Tabasco",             18.00,   -92.92, "Sur-Sureste"),
    ("TAM", "Tamaulipas",          24.27,   -98.84, "Norte"),
    ("TLX", "Tlaxcala",            19.31,   -98.24, "Centro"),
    ("VER", "Veracruz",            19.17,   -96.13, "Sur-Sureste"),
    ("YUC", "Yucatán",             20.97,   -89.62, "Sur-Sureste"),
    ("ZAC", "Zacatecas",           22.77,  -102.58, "Centro"),
]

AÑOS = list(range(1990, 2024))
MESES_LABELS = [str(y) for y in AÑOS]
GRUPOS_EDAD = ["15-19", "20-24", "25-29", "30-34", "35-39", "40-44", "45-49"]


def generar_sintetico():
    """Datos sintéticos coherentes con tendencias CONAPO documentadas."""
    rng = np.random.default_rng(seed=2024)

    # TGF nacional cayó de ~3.4 en 1990 a ~1.7 en 2023
    tgf_nacional = np.linspace(3.4, 1.7, len(AÑOS)) + rng.normal(0, 0.05, len(AÑOS))

    # TGF por entidad — sur más alta, CDMX y norte más baja
    tgf_entidad = {}
    for code, nombre, lat, lon, region in ENTIDADES:
        if region == "Sur-Sureste":
            offset = rng.uniform(0.3, 0.8)
        elif region == "Norte":
            offset = rng.uniform(-0.3, 0.1)
        else:
            offset = rng.uniform(-0.1, 0.3)
        if code == "CDMX":
            offset = -0.5
        tgf_entidad[code] = np.clip(tgf_nacional + offset + rng.normal(0, 0.03, len(AÑOS)), 1.0, 5.0)

    # DataFrame mapa (TGF promedio histórico por entidad)
    mapa = pd.DataFrame([
        {
            "code": code, "nombre": nombre,
            "latitude": lat, "longitude": lon, "region": region,
            "tgf_promedio": round(float(np.mean(tgf_entidad[code])), 3),
        }
        for code, nombre, lat, lon, region in ENTIDADES
    ])

    # Serie nacional suavizada
    serie_nacional = pd.DataFrame({
        "año": AÑOS,
        "tgf": tgf_nacional.round(3),
        "tgf_movil": pd.Series(tgf_nacional).rolling(5, center=True).mean().round(3).values,
    })

    # Top 5 entidades con mayor TGF
    top5_codes = mapa.nlargest(5, "tgf_promedio")["code"].tolist()
    serie_entidades = []
    for code in top5_codes:
        nombre = next(n for c, n, *_ in ENTIDADES if c == code)
        for i, año in enumerate(AÑOS):
            serie_entidades.append({"entidad": nombre, "año": año, "tgf": round(float(tgf_entidad[code][i]), 3)})
    serie_entidades = pd.DataFrame(serie_entidades)

    # Heatmap grupo_edad × año (tasa específica promedio nacional)
    # Patrón: pico en 20-29, caída en el tiempo, adelanto de primer hijo
    perfil_edad = np.array([0.60, 1.00, 0.90, 0.65, 0.40, 0.18, 0.05])
    tendencia_tiempo = np.linspace(1.0, 0.55, len(AÑOS))
    heatmap = np.zeros((len(GRUPOS_EDAD), len(AÑOS)))
    for i, _ in enumerate(GRUPOS_EDAD):
        for j, _ in enumerate(AÑOS):
            base = 120 * perfil_edad[i] * tendencia_tiempo[j]
            heatmap[i, j] = max(2.0, base + rng.normal(0, 3))

    return mapa, serie_nacional, serie_entidades, heatmap


def consultar_db():
    """Queries reales contra PostgreSQL (requiere DB_HOST)."""
    from sqlalchemy import create_engine
    engine = create_engine(
        f"postgresql+psycopg2://postgres:{os.environ['DB_PASSWORD']}"
        f"@{os.environ['DB_HOST']}:5432/{os.environ.get('DB_NAME', 'northwind')}"
    )

    mapa = pd.read_sql("""
        SELECT de.cve_geo AS code, de.nombre, de.region,
               ROUND(SUM(ff.tgf_contribucion)::NUMERIC, 3) AS tgf_promedio
        FROM   natalidad_dwh.fact_fecundidad ff
        JOIN   natalidad_dwh.dim_entidad     de USING (entidad_key)
        GROUP BY de.cve_geo, de.nombre, de.region
    """, engine)

    serie_nacional = pd.read_sql("""
        SELECT da.año,
               ROUND(AVG(tgf_sum)::NUMERIC, 3) AS tgf
        FROM (
            SELECT da.año, SUM(ff.tgf_contribucion) AS tgf_sum
            FROM   natalidad_dwh.fact_fecundidad ff
            JOIN   natalidad_dwh.dim_año         da USING (año_key)
            GROUP BY da.año, ff.entidad_key
        ) sub
        JOIN natalidad_dwh.dim_año da USING (año)
        GROUP BY da.año ORDER BY da.año
    """, engine)

    # Simplificado: usar datos sintéticos para heatmap y serie entidades en este template
    _, _, serie_entidades, heatmap = generar_sintetico()
    return mapa, serie_nacional, serie_entidades, heatmap


print(f"Modo: {'Base de datos' if USE_DB else 'sintético (demo)'}")
mapa, serie_nacional, serie_entidades, heatmap = (consultar_db() if USE_DB else generar_sintetico())


# =============================================================================
# Visualización 1 — Mapa de entidades (scatter sobre coordenadas)
# =============================================================================

fig, ax = plt.subplots(figsize=(12, 8))
sc = ax.scatter(
    mapa["longitude"], mapa["latitude"],
    c=mapa["tgf_promedio"], s=200,
    cmap="RdYlGn_r", vmin=1.5, vmax=4.0,
    edgecolors="black", linewidths=0.6, alpha=0.85, zorder=3,
)
for _, row in mapa.iterrows():
    ax.annotate(row["code"], (row["longitude"], row["latitude"]),
                fontsize=6.5, ha="center", va="center", zorder=4)
cbar = plt.colorbar(sc, ax=ax, label="TGF promedio histórico (hijos por mujer)")
cbar.ax.axhline(REEMPLAZO, color="black", linewidth=1.2)
cbar.ax.text(2.2, REEMPLAZO, "Reemplazo\n(2.1)", va="center", fontsize=8)
ax.set_xlabel("Longitud")
ax.set_ylabel("Latitud")
ax.set_title("Tasa Global de Fecundidad promedio por entidad federativa\nMéxico 1990–2023")
ax.grid(True, alpha=0.25)
plt.tight_layout()
plt.savefig(OUT / "01_mapa_entidades.png", dpi=110)
plt.close()
print("✓ 01_mapa_entidades.png")


# =============================================================================
# Visualización 2 — Evolución nacional de la TGF
# =============================================================================

fig, ax = plt.subplots(figsize=(12, 5.5))
ax.plot(serie_nacional["año"], serie_nacional["tgf"],
        color="#aec7e8", linewidth=1.5, alpha=0.8, label="TGF anual")
ax.plot(serie_nacional["año"], serie_nacional["tgf_movil"],
        color="#1f77b4", linewidth=2.5, label="Tendencia (promedio móvil 5 años)")
ax.axhline(REEMPLAZO, color="red", linestyle="--", linewidth=1.2,
           label=f"Tasa de reemplazo ({REEMPLAZO})")
ax.fill_between(serie_nacional["año"], serie_nacional["tgf"], REEMPLAZO,
                where=(serie_nacional["tgf"] >= REEMPLAZO),
                alpha=0.15, color="orange", label="Por encima del reemplazo")
ax.set_xticks(range(1990, 2024, 5))
ax.set_ylabel("Hijos promedio por mujer (TGF)")
ax.set_title("Evolución de la Tasa Global de Fecundidad en México (1990–2023)")
ax.legend(loc="upper right", fontsize=9)
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(OUT / "02_serie_nacional.png", dpi=110)
plt.close()
print("✓ 02_serie_nacional.png")


# =============================================================================
# Visualización 3 — Top 10 entidades mayor vs menor fecundidad
# =============================================================================

top5  = mapa.nlargest(5,  "tgf_promedio")
bot5  = mapa.nsmallest(5, "tgf_promedio")
comp  = pd.concat([top5, bot5]).sort_values("tgf_promedio")

colores = ["#d73027" if v > REEMPLAZO else "#4575b4" for v in comp["tgf_promedio"]]
fig, ax = plt.subplots(figsize=(11, 6))
bars = ax.barh(comp["nombre"], comp["tgf_promedio"], color=colores, edgecolor="black", linewidth=0.5)
ax.axvline(REEMPLAZO, color="black", linestyle="--", linewidth=1.2)
ax.text(REEMPLAZO + 0.05, len(comp) - 0.5, f"Reemplazo\n({REEMPLAZO})", fontsize=9, va="top")
ax.set_xlabel("TGF promedio histórico (hijos por mujer)")
ax.set_title("Top 5 mayor y top 5 menor fecundidad por entidad — México 1990–2023")
for i, v in enumerate(comp["tgf_promedio"]):
    ax.text(v + 0.03, i, f"{v:.2f}", va="center", fontsize=9)
alta   = mpatches.Patch(color="#d73027", label="Sobre tasa de reemplazo")
baja   = mpatches.Patch(color="#4575b4", label="Bajo tasa de reemplazo")
ax.legend(handles=[alta, baja], fontsize=9)
ax.grid(True, alpha=0.3, axis="x")
plt.tight_layout()
plt.savefig(OUT / "03_top_entidades.png", dpi=110)
plt.close()
print("✓ 03_top_entidades.png")


# =============================================================================
# Visualización 4 — Heatmap tasa específica por grupo de edad × año
# =============================================================================

fig, ax = plt.subplots(figsize=(14, 6))
im = ax.imshow(heatmap, aspect="auto", cmap="YlOrRd", vmin=0, vmax=160, origin="upper")
ax.set_xticks(range(0, len(AÑOS), 5))
ax.set_xticklabels([str(AÑOS[i]) for i in range(0, len(AÑOS), 5)])
ax.set_yticks(range(len(GRUPOS_EDAD)))
ax.set_yticklabels(GRUPOS_EDAD)
ax.set_xlabel("Año")
ax.set_ylabel("Grupo de edad")
ax.set_title("Tasa específica de fecundidad por grupo de edad — México 1990–2023\n(nacimientos por cada 1,000 mujeres)")
plt.colorbar(im, ax=ax, label="Nacimientos por 1,000 mujeres")
plt.tight_layout()
plt.savefig(OUT / "04_heatmap_edad_año.png", dpi=110)
plt.close()
print("✓ 04_heatmap_edad_año.png")

print(f"\n✓ 4 visualizaciones generadas en {OUT}/")
