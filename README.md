# 🚴 Ride Analytics — Dashboard de ciclismo con datos de Garmin

Dashboard interactivo que transforma los archivos `.fit` de un ciclocomputador Garmin en métricas de rendimiento, visualizaciones y conclusiones automáticas. Lo construí para analizar mis propias salidas y responder preguntas como *¿qué tan intensa fue esta salida?*, *¿en qué zonas entrené?* o *¿estoy mejorando mi eficiencia aeróbica?*

![Vista general](docs/screenshots/actividad.png)

## ¿Qué hace?

| Sección | Qué muestra |
|---|---|
| **KPIs** | Distancia, tiempo en movimiento, velocidad, desnivel, potencia media y normalizada, TSS, FC y cadencia |
| **Lo que dicen los datos** | Conclusiones generadas automáticamente a partir de las métricas (intensidad, variabilidad, tiempo sin pedalear, fatiga) |
| **Ruta** | Mapa interactivo con el trazado coloreado por velocidad, potencia, FC o altitud |
| **Rendimiento** | Altitud, velocidad, potencia, FC y cadencia alineadas por distancia (*small multiples*, sin gráficos de doble eje) |
| **Zonas** | Distribución del tiempo en zonas de potencia (Coggan) y de frecuencia cardíaca |
| **Curva de potencia** | Mejor potencia sostenida de 5 s a 2 h |
| **Parciales** | Velocidad, potencia, FC y desnivel cada 1, 5 o 10 km |
| **Datos y calidad** | Validación de los cálculos contra el dispositivo, % de datos faltantes y exportación a CSV |
| **Historial** | Comparación entre actividades: distancia, carga, velocidad y factor de eficiencia |

![Zonas de entrenamiento](docs/screenshots/zonas.png)
![Historial](docs/screenshots/historial.png)

## Métricas calculadas

Todas las métricas avanzadas se calculan **desde los datos crudos segundo a segundo** (no se copian del resumen de Garmin):

- **Potencia normalizada (NP):** media móvil de 30 s → potencia a la 4ª → media → raíz 4ª. Pondera más los esfuerzos intensos que la potencia media.
- **Intensity Factor (IF)** = NP / FTP, y **Training Stress Score (TSS)** = duración × NP × IF / (FTP × 3600) × 100.
- **Índice de variabilidad (VI)** = NP / potencia media. Indica qué tan constante fue el esfuerzo.
- **Factor de eficiencia (EF)** = NP / FC media. Mide los vatios producidos por latido.
- **Desacople aeróbico (Pw:HR):** caída de la relación potencia/FC entre la primera y la segunda mitad.
- **Curva de potencia:** máximo de la media móvil para cada duración.

### Validación

Mis cálculos se comparan con los valores que calcula el propio Garmin y quedan dentro de un **±0,5 %**:

| Actividad | NP calculada | NP Garmin | TSS calculado | TSS Garmin |
|---|---|---|---|---|
| 06 ene 2026 | 201,6 W | 202 W | 86,9 | 87,2 |
| 08 ene 2026 | 219,7 W | 220 W | 142,3 | 142,2 |
| 10 ene 2026 | 209,5 W | 210 W | 184,4 | 184,6 |

Esta comparación también corre como test automático (`tests/test_ingestion_metrics.py`).

## Arquitectura

El proyecto sigue un pipeline de datos en capas: cada capa tiene una única responsabilidad y la lógica de análisis no depende de Streamlit, por lo que se puede testear por separado.

```
archivo .fit
   │
   ▼
src/ingestion/      fit_loader.py   → Lee el FIT, convierte unidades (semicírculos → grados,
   │                                  m/s → km/h), ajusta la hora UTC a hora local
   ▼
src/processing/     metrics.py      → Resumen de la sesión (tolerante a sensores faltantes)
   │                performance.py  → NP, IF, TSS, zonas, curva de potencia, parciales
   │                insights.py     → Conclusiones en lenguaje natural
   ▼
src/visualization/  charts.py       → Gráficos Plotly
   │                maps.py         → Mapa Folium coloreado por métrica
   │                theme.py        → Paleta de colores y estilo compartido
   ▼
app/                streamlit_app.py → Navegación
                    views/           → Páginas "Actividad" e "Historial"
```

```
dashboard-bike/
├── app/
│   ├── streamlit_app.py
│   └── views/
│       ├── actividad.py
│       └── resumen.py
├── src/
│   ├── ingestion/fit_loader.py
│   ├── processing/{metrics,performance,insights}.py
│   ├── visualization/{charts,maps,theme}.py
│   └── ui/components.py         ← Tarjetas KPI, estilos y carga con caché
├── tests/
├── data/raw/fit/                ← Archivos .fit
├── .streamlit/config.toml       ← Tema oscuro
└── requirements.txt
```

### Decisiones técnicas

- **Valores faltantes como `None`, no como `0`:** así "sin medidor de potencia" no se confunde con "0 W", y la interfaz muestra "—".
- **Caché (`st.cache_data`):** cada archivo se lee una sola vez. La fecha de modificación forma parte de la clave, así que un archivo que cambia se vuelve a leer.
- **Small multiples en lugar de doble eje:** cada métrica tiene su propia escala, alineadas por distancia.
- **Hora local:** los FIT guardan la hora en UTC; el desfase se obtiene del mensaje `activity` del propio archivo.
- **Reducción de puntos en el mapa:** máximo 4.000 puntos, para que cargue rápido sin perder la forma de la ruta.

## Cómo ejecutarlo

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt

streamlit run app/streamlit_app.py
```

Coloca tus archivos `.fit` en `data/raw/fit/` o súbelos desde la barra lateral. Puedes exportarlos desde Garmin Connect: *Actividad → ⚙️ → Exportar original*.

> Las actividades no están incluidas en el repositorio porque contienen datos GPS personales.

### Tests

```bash
pytest
```

La validación contra Garmin se ejecuta solo si hay archivos `.fit` en `data/raw/fit/`; si no los hay, esos tests se omiten.

## Tecnologías

Python · pandas · NumPy · Streamlit · Plotly · Folium · fitparse · pytest

## Próximos pasos

- Carga crónica y aguda (CTL / ATL / TSB) para modelar la forma física en el tiempo.
- Detección automática de subidas y cálculo de VAM.
- Conexión directa con la API de Garmin o Strava.
