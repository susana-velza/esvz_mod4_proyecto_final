"""
Dashboard — Perfil sociodemográfico de madres en México (2010–2018)

Alumna: Elizabeth Susana Velázquez Zamora
Módulo 4 · Diplomado SQL-NoSQL · IIMAS, UNAM

Uso:
    streamlit run dashboard/app.py -- \\
        --host TU_HOST \\
        --password TU_PASSWORD \\
        --database northwind

Si no se pasan argumentos de conexión, el dashboard corre con datos
sintéticos coherentes con el dataset real — útil para previsualizar
sin conexión a Aurora.
"""

import sys
import argparse
import os

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# =============================================================================
# Configuración de página
# =============================================================================

st.set_page_config(
    page_title="Nacimientos México · IIMAS",
    page_icon="👶",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =============================================================================
# Parámetros de conexión (argumentos CLI o variables de entorno)
# =============================================================================

def parse_args():
    parser = argparse.ArgumentParser()
    # Lee primero desde variables de entorno; los argumentos CLI tienen prioridad
    parser.add_argument("--host",     default=os.environ.get("AURORA_HOST", ""))
    parser.add_argument("--password", default=os.environ.get("AURORA_PASSWORD", ""))
    parser.add_argument("--database", default=os.environ.get("AURORA_DATABASE", "northwind"))
    args, _ = parser.parse_known_args()
    return args

args = parse_args()
USE_AURORA = bool(args.host and args.password)

# =============================================================================
# Carga de datos (Aurora o sintéticos)
# =============================================================================

ESTADOS_MEXICO = [
    "Aguascalientes", "Baja California", "Baja California Sur", "Campeche",
    "Coahuila", "Colima", "Chiapas", "Chihuahua", "Ciudad de México",
    "Durango", "Guanajuato", "Guerrero", "Hidalgo", "Jalisco",
    "Estado de México", "Michoacán", "Morelos", "Nayarit", "Nuevo León",
    "Oaxaca", "Puebla", "Querétaro", "Quintana Roo", "San Luis Potosí",
    "Sinaloa", "Sonora", "Tabasco", "Tamaulipas", "Tlaxcala",
    "Veracruz", "Yucatán", "Zacatecas",
]

GRUPOS_EDAD = ["< 15", "15-19", "20-24", "25-29", "30-34", "35+"]
ESCOLARIDADES = ["Sin escolaridad", "Primaria", "Secundaria", "Media superior", "Superior"]
REGIONES = {"Norte": ["Baja California","Baja California Sur","Chihuahua","Coahuila","Durango",
                      "Nayarit","Nuevo León","Sinaloa","Sonora","Tamaulipas"],
            "Centro": ["Aguascalientes","Ciudad de México","Colima","Estado de México",
                       "Guanajuato","Hidalgo","Jalisco","Michoacán","Morelos","Puebla",
                       "Querétaro","San Luis Potosí","Tlaxcala","Zacatecas"],
            "Sur-Sureste": ["Campeche","Chiapas","Guerrero","Oaxaca","Quintana Roo",
                            "Tabasco","Veracruz","Yucatán"]}

def region_de(estado):
    for reg, estados in REGIONES.items():
        if estado in estados:
            return reg
    return "Centro"


@st.cache_data(ttl=300)
def cargar_datos_aurora():
    from sqlalchemy import create_engine
    engine = create_engine(
        f"postgresql+psycopg2://postgres:{args.password}@{args.host}:5432/{args.database}"
    )
    with engine.connect() as conn:
        df = pd.read_sql("""
            SELECT
                dd.anio,
                de.nombre_estado,
                de.region,
                de.zona,
                dm.grupo_edad,
                dm.is_adolescente,
                dm.escolaridad,
                dm.nivel_escolar,
                dm.estado_civil,
                SUM(fn.total_nacimientos) AS nacimientos
            FROM   nacimientos_dwh.fact_nacimientos fn
            JOIN   nacimientos_dwh.dim_fecha        dd USING (fecha_key)
            JOIN   nacimientos_dwh.dim_estado       de USING (estado_key)
            JOIN   nacimientos_dwh.dim_madre        dm USING (madre_key)
            GROUP BY dd.anio, de.nombre_estado, de.region, de.zona,
                     dm.grupo_edad, dm.is_adolescente,
                     dm.escolaridad, dm.nivel_escolar, dm.estado_civil
            ORDER BY dd.anio, de.nombre_estado
        """, conn)
    return df


def generar_datos_sinteticos():
    rng = np.random.default_rng(42)
    rows = []

    # Parámetros de tendencia por región
    tendencia_escol = {"Norte": 0.04, "Centro": 0.03, "Sur-Sureste": 0.015}
    base_adolesc = {"Norte": 0.14, "Centro": 0.16, "Sur-Sureste": 0.23}
    dist_esc_base = {
        "Norte":       [0.02, 0.12, 0.30, 0.35, 0.21],
        "Centro":      [0.03, 0.15, 0.32, 0.32, 0.18],
        "Sur-Sureste": [0.06, 0.22, 0.35, 0.26, 0.11],
    }

    for estado in ESTADOS_MEXICO:
        reg = region_de(estado)
        for anio in range(2010, 2019):
            t = anio - 2010
            # Nacimientos totales (decrecientes ~1.5% anual)
            base_nac = rng.integers(12000, 55000)
            total = int(base_nac * (0.985 ** t))

            # Distribución de grupos de edad
            p_adol = max(0.05, base_adolesc[reg] - t * 0.008 + rng.normal(0, 0.01))
            pesos_edad = [
                max(0.01, p_adol * 0.12),
                max(0.04, p_adol * 0.88),
                0.32, 0.28, 0.15, 0.08,
            ]
            pesos_edad = np.array(pesos_edad) / sum(pesos_edad)

            for i, grupo in enumerate(GRUPOS_EDAD):
                nac_grupo = int(total * pesos_edad[i])
                is_adol = grupo in ("< 15", "15-19")

                # Distribución de escolaridad (mejora con el tiempo)
                dist_e = np.array(dist_esc_base[reg].copy())
                dist_e[3] += t * tendencia_escol[reg]
                dist_e[4] += t * tendencia_escol[reg] * 0.6
                dist_e[0] -= t * tendencia_escol[reg] * 0.3
                dist_e[1] -= t * tendencia_escol[reg] * 0.7
                dist_e = np.clip(dist_e, 0.01, None)
                dist_e /= dist_e.sum()

                for j, esc in enumerate(ESCOLARIDADES):
                    nac_esc = int(nac_grupo * dist_e[j])
                    if nac_esc <= 0:
                        continue

                    # Estado civil
                    if is_adol:
                        dist_civil = [0.35, 0.15, 0.45, 0.05]
                    else:
                        dist_civil = [0.10, 0.45, 0.42, 0.03]

                    civiles = ["Soltera", "Casada", "Unión libre", "Otro"]
                    for k, civil in enumerate(civiles):
                        nac_civil = int(nac_esc * dist_civil[k])
                        if nac_civil <= 0:
                            continue
                        rows.append({
                            "anio":          anio,
                            "nombre_estado": estado,
                            "region":        reg,
                            "zona":          reg.lower().replace("-sureste", "").replace("sur", "sur"),
                            "grupo_edad":    grupo,
                            "is_adolescente": is_adol,
                            "escolaridad":   esc,
                            "nivel_escolar": j,
                            "estado_civil":  civil,
                            "nacimientos":   nac_civil,
                        })
    return pd.DataFrame(rows)


@st.cache_data
def cargar_datos():
    if USE_AURORA:
        return cargar_datos_aurora()
    return generar_datos_sinteticos()


df = cargar_datos()

# =============================================================================
# Sidebar — Filtros
# =============================================================================

st.sidebar.title("Filtros")
st.sidebar.markdown("---")

anios_disp = sorted(df["anio"].unique())
anio_sel = st.sidebar.select_slider(
    "Año", options=anios_disp, value=(anios_disp[0], anios_disp[-1])
)

regiones_disp = ["Todas"] + sorted(df["region"].unique())
region_sel = st.sidebar.selectbox("Región", regiones_disp)

estados_disp = (
    sorted(df["nombre_estado"].unique())
    if region_sel == "Todas"
    else sorted(df[df["region"] == region_sel]["nombre_estado"].unique())
)
estado_sel = st.sidebar.multiselect(
    "Estado(s)", estados_disp, default=estados_disp[:5]
)

st.sidebar.markdown("---")
st.sidebar.caption(
    f"{'🔴 Conectado a Aurora' if USE_AURORA else '🟡 Datos sintéticos (sin Aurora)'}"
)

# Aplicar filtros
mask = (
    (df["anio"] >= anio_sel[0]) &
    (df["anio"] <= anio_sel[1])
)
if region_sel != "Todas":
    mask &= df["region"] == region_sel
if estado_sel:
    mask &= df["nombre_estado"].isin(estado_sel)

dff = df[mask].copy()

# =============================================================================
# Header
# =============================================================================

st.title("👶 Nacimientos en México · Perfil de la madre (2010–2018)")
st.caption(
    "Datos sintéticos basados en patrones documentados del INEGI/SINAC · "
    "Módulo 4 — Diplomado SQL-NoSQL · IIMAS, UNAM · "
    "Elizabeth Susana Velázquez Zamora"
)
st.markdown("---")

# KPIs
col1, col2, col3, col4 = st.columns(4)
total_nac = dff["nacimientos"].sum()
pct_adol = (
    dff[dff["is_adolescente"]]["nacimientos"].sum() / total_nac * 100
    if total_nac > 0 else 0
)
pct_media_sup = (
    dff[dff["nivel_escolar"] >= 3]["nacimientos"].sum() / total_nac * 100
    if total_nac > 0 else 0
)
pct_soltera = (
    dff[dff["estado_civil"] == "Soltera"]["nacimientos"].sum() / total_nac * 100
    if total_nac > 0 else 0
)

col1.metric("Total nacimientos", f"{total_nac:,.0f}")
col2.metric("Madres adolescentes", f"{pct_adol:.1f}%")
col3.metric("Media superior o más", f"{pct_media_sup:.1f}%")
col4.metric("Madres solteras", f"{pct_soltera:.1f}%")

st.markdown("---")

# =============================================================================
# Visualización 1 — Evolución temporal de grupos de edad (línea)
# =============================================================================

st.subheader("1 · Evolución de la maternidad por grupo de edad")
st.caption("¿Cómo cambia la distribución de edad de las madres a lo largo del periodo?")

evol_edad = (
    dff.groupby(["anio", "grupo_edad"])["nacimientos"]
    .sum()
    .reset_index()
)
evol_edad_pct = evol_edad.copy()
totales_anio = evol_edad.groupby("anio")["nacimientos"].sum().rename("total")
evol_edad_pct = evol_edad_pct.merge(totales_anio, on="anio")
evol_edad_pct["pct"] = evol_edad_pct["nacimientos"] / evol_edad_pct["total"] * 100

orden_edad = ["< 15", "15-19", "20-24", "25-29", "30-34", "35+"]
evol_edad_pct["grupo_edad"] = pd.Categorical(
    evol_edad_pct["grupo_edad"], categories=orden_edad, ordered=True
)
evol_edad_pct = evol_edad_pct.sort_values(["anio", "grupo_edad"])

fig1 = px.line(
    evol_edad_pct,
    x="anio", y="pct", color="grupo_edad",
    category_orders={"grupo_edad": orden_edad},
    labels={"anio": "Año", "pct": "% del total de nacimientos", "grupo_edad": "Grupo de edad"},
    markers=True,
    color_discrete_sequence=px.colors.qualitative.Set2,
)
fig1.update_layout(
    hovermode="x unified",
    legend_title="Grupo de edad",
    margin=dict(t=20, b=20),
)
st.plotly_chart(fig1, use_container_width=True)

# =============================================================================
# Visualización 2 — Escolaridad de la madre por región (barras apiladas)
# =============================================================================

st.subheader("2 · Nivel de escolaridad de las madres por región")
st.caption("¿Qué tan diferente es el perfil educativo entre el norte, centro y sur del país?")

escol_region = (
    dff.groupby(["region", "escolaridad", "nivel_escolar"])["nacimientos"]
    .sum()
    .reset_index()
    .sort_values("nivel_escolar")
)
totales_region = escol_region.groupby("region")["nacimientos"].sum().rename("total")
escol_region = escol_region.merge(totales_region, on="region")
escol_region["pct"] = escol_region["nacimientos"] / escol_region["total"] * 100

orden_escol = ["Sin escolaridad", "Primaria", "Secundaria", "Media superior", "Superior"]
escol_region["escolaridad"] = pd.Categorical(
    escol_region["escolaridad"], categories=orden_escol, ordered=True
)

fig2 = px.bar(
    escol_region.sort_values(["region", "nivel_escolar"]),
    x="region", y="pct", color="escolaridad",
    category_orders={"escolaridad": orden_escol},
    labels={"region": "Región", "pct": "% de nacimientos", "escolaridad": "Escolaridad"},
    color_discrete_sequence=["#d73027", "#fc8d59", "#fee090", "#91bfdb", "#4575b4"],
    barmode="stack",
)
fig2.update_layout(
    legend_title="Nivel educativo",
    margin=dict(t=20, b=20),
    yaxis_ticksuffix="%",
)
st.plotly_chart(fig2, use_container_width=True)

# =============================================================================
# Visualización 3 — Mapa de calor: % madres adolescentes por estado y año
# =============================================================================

st.subheader("3 · % de maternidad adolescente por estado y año")
st.caption("¿Qué entidades concentran la mayor proporción de madres menores de 20 años, y cómo ha evolucionado?")

adol_estado_anio = (
    dff.groupby(["nombre_estado", "anio"])
    .agg(
        adolescentes=("nacimientos", lambda x: x[dff.loc[x.index, "is_adolescente"]].sum()),
        total=("nacimientos", "sum"),
    )
    .reset_index()
)
adol_estado_anio["pct_adol"] = (
    adol_estado_anio["adolescentes"] / adol_estado_anio["total"] * 100
).round(2)

# Pivot para heatmap
pivot = adol_estado_anio.pivot(
    index="nombre_estado", columns="anio", values="pct_adol"
).fillna(0)

# Ordenar por promedio descendente
pivot["_media"] = pivot.mean(axis=1)
pivot = pivot.sort_values("_media", ascending=True).drop(columns="_media")

fig3 = go.Figure(data=go.Heatmap(
    z=pivot.values,
    x=[str(c) for c in pivot.columns],
    y=pivot.index.tolist(),
    colorscale="RdYlGn_r",
    colorbar=dict(title="% adolescentes"),
    hovertemplate="Estado: %{y}<br>Año: %{x}<br>% adolescentes: %{z:.1f}%<extra></extra>",
))
fig3.update_layout(
    xaxis_title="Año",
    yaxis_title="Estado",
    margin=dict(t=20, b=20, l=180),
    height=700,
)
st.plotly_chart(fig3, use_container_width=True)

# =============================================================================
# Visualización 4 — Distribución de estado civil por región y periodo
# =============================================================================

st.subheader("4 · Estado civil de las madres: comparativa por región y periodo")
st.caption("¿Cómo cambió la composición familiar entre la primera y segunda mitad del periodo?")

dff["periodo"] = dff["anio"].apply(
    lambda a: "2010–2014" if a <= 2014 else "2015–2018"
)
civil_region = (
    dff.groupby(["region", "periodo", "estado_civil"])["nacimientos"]
    .sum()
    .reset_index()
)
totales_rp = civil_region.groupby(["region", "periodo"])["nacimientos"].sum().rename("total")
civil_region = civil_region.merge(totales_rp, on=["region", "periodo"])
civil_region["pct"] = civil_region["nacimientos"] / civil_region["total"] * 100

fig4 = px.bar(
    civil_region,
    x="pct", y="region", color="estado_civil",
    facet_col="periodo",
    labels={"pct": "% nacimientos", "region": "Región", "estado_civil": "Estado civil"},
    color_discrete_map={
        "Casada":      "#4575b4",
        "Unión libre": "#91bfdb",
        "Soltera":     "#d73027",
        "Otro":        "#aaa",
    },
    orientation="h",
    barmode="stack",
)
fig4.update_layout(
    legend_title="Estado civil",
    margin=dict(t=40, b=20),
    xaxis_ticksuffix="%",
    xaxis2_ticksuffix="%",
)
st.plotly_chart(fig4, use_container_width=True)

# =============================================================================
# Footer
# =============================================================================

st.markdown("---")
st.caption(
    "Datos sintéticos generados con distribuciones basadas en patrones documentados del INEGI/SINAC, 2010–2018. "
    "Dataset de referencia: Kaggle `emmanuelleai/nacimientos-en-mxico` · "
    "Procesado con pandas + SQLAlchemy · Aurora PostgreSQL"
)
