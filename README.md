# NASA Space Apps Challenge 2026 — Harmonizing MODIS and VIIRS Hotspots

Web app that harmonizes MODIS (2000+) and VIIRS S-NPP (2012+) active-fire hotspots into a
burning-activity calendar for a selected area of interest (pilot: Tolima, Colombia).

## Estructura
- `index.html` — la aplicación web (sitio estático, GitHub Pages). Hoy usa datos sintéticos de demostración.
- `pipeline/config.py` — área de interés (rectángulo sobre el Tolima) y bandas de latitud.
- `pipeline/download_firms.py` — descarga hotspots de NASA FIRMS y los agrega a celdas de 0,25° por semana.
- `pipeline/harmonize.py` — calibra MODIS contra VIIRS en el solapamiento (2012+) y exporta `data/harmonized.json`.
- `data/` — datos agregados y resultados (`data/raw/` no se sube).

## Cómo ejecutar el pipeline
1. `pip install -r requirements.txt`
2. Abre `MAP_KEY.txt`, borra el texto y pega tu MAP_KEY de FIRMS (el archivo no se sube al repo).
3. Año de prueba: `python pipeline/download_firms.py --start 2019`
4. Histórico: `python pipeline/download_firms.py --start 2000 --end 2025` (reanuda si se corta)
5. Armonizar: `python pipeline/harmonize.py`

## Método
1. Hotspots de FIRMS (`MODIS_SP`, `VIIRS_SNPP_SP`) filtrados por confianza y agregados a grilla de 0,25° y semana.
2. Fuentes fijas (industriales/gas/urbanas) detectadas y excluidas.
3. Factor de calibración k = ΣVIIRS / ΣMODIS en el solapamiento, por banda de latitud y mes.
4. Serie armonizada = MODIS×k antes de 2012 y VIIRS después.
5. Anomalías (z) contra la climatología semanal y detección de periodos críticos.
6. Validación: R² y sesgo en el solapamiento; comparación opcional con cicatrices de quema de Sentinel-2.

## Créditos de datos
NASA FIRMS (MODIS, VIIRS) · Sentinel-2 cloudless by EOX IT Services GmbH (Contains modified Copernicus Sentinel data 2020) · © OpenStreetMap contributors.
