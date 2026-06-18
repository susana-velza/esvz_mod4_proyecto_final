# Dataset — Nacimientos en México (INEGI 2010–2018)

El archivo CSV no se incluye en el repositorio por su tamaño.

## Descarga

**Opción A — Kaggle CLI:**
```bash
pip install kaggle
# Configurar ~/.kaggle/kaggle.json con tu API key
kaggle datasets download -d emmanuelleai/nacimientos-en-mxico -p datasets/
unzip datasets/nacimientos-en-mxico.zip -d datasets/
```

**Opción B — Descarga manual:**
1. Ir a https://www.kaggle.com/datasets/emmanuelleai/nacimientos-en-mxico
2. Descargar el archivo CSV
3. Guardarlo como `datasets/nacimientos_mexico.csv`

## Descripción del dataset

| Campo | Descripción |
|---|---|
| Fuente | INEGI — Sistema de Información de Nacimientos (SINAC) |
| Periodo | 2010–2018 |
| Granularidad | Nacimientos agrupados por estado, año, sexo del bebé, edad de la madre, escolaridad y estado civil |
| Filas aprox. | 300,000+ |
| Licencia | Datos públicos del gobierno mexicano |

