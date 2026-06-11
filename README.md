# Proyecto Final — Módulo 4: BI y SQL Avanzado
## Natalidad en México: Tasa Global de Fecundidad (1990–2023)

**Alumna:** Elizabeth Susana Velázquez Zamora 
**Profesor:** Oscar Alvarez  
**Repositorio:** https://github.com/susana-velza/esvz_mod4_proyecto_final

---

## Descripción del proyecto

Este proyecto analiza la evolución de la natalidad en México a lo largo de las décadas,
con foco en la **Tasa Global de Fecundidad (TGF)**: el promedio de hijos que tiene una
mujer a lo largo de su vida fértil. Se construye un Data Warehouse dimensional en
PostgreSQL, se carga el CSV de datos del INEGI/CONAPO y se ejecutan cinco queries
analíticas con técnicas avanzadas de SQL (CTEs, window functions, funciones de orden
estadístico).

---

## Pregunta de negocio

> ¿Cómo ha evolucionado el número de hijos promedio por mujer en México entre 1990 y 2023,
> y qué diferencias existen entre entidades federativas y grupos de edad?

---

## Fuente de datos

| Fuente | Dataset | URL |
|--------|---------|-----|
| CONAPO | Indicadores demográficos 1950–2050 | https://www.gob.mx/conapo/documentos/indicadores-demograficos-1950-2070 |
| INEGI  | Estadísticas de natalidad | https://www.inegi.org.mx/temas/natalidad/ |

> El CSV principal se coloca en `data/natalidad_mexico.csv` antes de correr el ETL.

---

## Modelo dimensional

--Pendiente

**Grano:** una fila por (año × entidad federativa × grupo de edad)  
**Medidas:** `tasa_especifica`, `nacimientos`, `mujeres_en_edad_fertil`

---

## Estructura del repositorio

```
esvz_mod4_proyecto_final/
│
├── data/
│   └── natalidad_mexico.csv        
│
├── sql/
│   ├── 01_schema_ddl.sql          
│   ├── 02_dim_año_populate.sql     
│   ├── 03_dim_entidad_populate.sql 
│   ├── 04_dim_grupo_edad_populate.sql
│   └── queries_analiticas.sql      -- pendiente
│
├── etl_pipeline.py                
├── generar_visualizaciones.py      
└── README.md
```

---

## Cómo ejecutar

### 1. Requisitos
```bash
pip install pandas sqlalchemy psycopg2-binary matplotlib tqdm
```

### 2. Crear tablas
```bash
psql -h <host> -U postgres -d <database> -f sql/01_schema_ddl.sql
psql -h <host> -U postgres -d <database> -f sql/02_dim_año_populate.sql
psql -h <host> -U postgres -d <database> -f sql/03_dim_entidad_populate.sql
psql -h <host> -U postgres -d <database> -f sql/04_dim_grupo_edad_populate.sql
```

### 3. Cargar datos
```bash
python etl_pipeline.py \
    --host <aurora-host> \
    --password <password> \
    --database <database> \
    --csv data/natalidad_mexico.csv
```

### 4. Correr queries analíticas
```bash
psql -h <host> -U postgres -d <database> -f sql/queries_analiticas.sql
```

### 5. Generar visualizaciones
```bash
python generar_visualizaciones.py
# Las imágenes quedan en dashboard/img/
```

---

## Queries analíticas (resumen)

| # | Técnica | Pregunta que responde |
|---|---------|----------------------|
| 1 | CTE + ranking | Top 5 entidades con mayor TGF promedio |
| 2 | Window function (promedio móvil) | Tendencia suavizada de fecundidad a lo largo de los años |
| 3 | COUNT FILTER | % de años por entidad en que la TGF estuvo por encima del reemplazo (2.1) |
| 4 | PERCENTILE_CONT | Mediana y percentil 95 de nacimientos por grupo de edad |
| 5 | CTE + LAG | Entidades con mayor caída de fecundidad año a año |

---

## Visualizaciones

| Archivo | Descripción |
|---------|-------------|
| `01_mapa_entidades.png` | Mapa de México coloreado por TGF promedio |
| `02_serie_nacional.png` | Evolución nacional de la TGF 1990–2023 |
| `03_top_entidades.png`  | Top 10 entidades con mayor vs menor fecundidad |
| `04_heatmap_edad_año.png` | Heatmap tasa de fecundidad por grupo de edad y año |
