# Guion del pitch (borrador) — ~3 min

> Los números entre [corchetes] se rellenan cuando corra `harmonize.py` con los datos reales.

## 1. Problema (30 s)
- Los satélites detectan fuegos activos desde el año 2000, pero el registro está partido en dos:
  **MODIS** (1 km, desde 2000) y **VIIRS** (375 m, desde 2012).
- VIIRS ve fuegos más pequeños, así que detecta **[k]× más hotspots** en el mismo lugar y semana.
- Si se pegan las dos series sin corregir, en 2012 aparece un "aumento del fuego" que es en realidad
  **un cambio de sensor**. Eso engaña a quien busca tendencias o periodos anómalos.

## 2. Nuestra solución (45 s)
- Un **calendario de actividad de quema** (año × semana) para el **Tolima, Colombia**, 2000–2025.
- Armonización: en los años en que ambos sensores operan (2012–2025) calculamos
  **k = Σ VIIRS / Σ MODIS** por **franja de latitud** (norte/centro/sur) y **mes**, y re-escalamos
  MODIS antes de 2012. Resultado: una sola serie continua de 26 años en "unidades VIIRS".
- Limpieza: quitamos **fuentes fijas** (zonas urbanas, industria, volcán) que no son quemas.

## 3. Demo (60 s)
1. Elegir el AOI tocando celdas en el mapa (o un preset Norte/Centro/Sur).
2. Calendario **Crudo vs Armonizado**: mostrar el salto de 2012 que desaparece.
3. Vista **Anomalía (z)**: qué semanas fueron inusuales respecto a su propia época del año.
4. **Periodos críticos**: lista automática; clic y se resalta en el calendario.
5. Mencionar la temporada típica del Tolima: [semana pico].

## 4. Validación (20 s)
- En el solapamiento, MODIS×k reproduce VIIRS con **R² semanal = [norte / centro / sur]** y
  sesgo **[x %]**.
- [Opcional] Un periodo crítico verificado con cicatrices de quema en Sentinel-2.

## 5. Limitaciones (15 s)
- Un hotspot no es una hectárea quemada: medimos **actividad de detección**, no área.
- Nubosidad y horario de paso del satélite afectan las detecciones (temporada húmeda andina).
- k se asume constante en el tiempo; el AOI es un rectángulo (incluye bordes de departamentos vecinos)
  [salvo que se aplique el polígono].
- Solo VIIRS S-NPP; NOAA-20/21 quedan fuera.

## 6. Trabajo futuro (10 s)
- Cualquier región del mundo (el pipeline solo cambia el `config.py`).
- Añadir NOAA-20/21, área quemada (MCD64A1) y meteorología (sequía, ENSO).
- Alertas: avisar cuando la semana actual supere el z crítico.

## Para quién
Alerta temprana, respuesta a emergencias (bomberos, CAR, UNGRD), científicos y gestores de tierras.
