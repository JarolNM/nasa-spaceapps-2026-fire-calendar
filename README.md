# NASA Space Apps Challenge 2026 — Harmonizing MODIS and VIIRS Hotspots

Web app that harmonizes MODIS (2000+) and VIIRS S-NPP (2012+) active-fire hotspots into a
burning-activity calendar for a selected area of interest (pilot: Tolima, Colombia).

## Estructura
- `index.html` — la aplicación web (sitio estático, GitHub Pages). Lee `data/hotspots.json`.
- `pipeline/points.py` — une los CSV crudos, quita duplicados, clasifica confianza, asigna municipio (DANE) y exporta `data/hotspots.json` + `data/validation.json`.
- `pipeline/tolima_mask.py` — utilidades para leer el GeoPackage del DANE (y máscara de celdas 0,25°, versión anterior).
- `pipeline/config.py` — área de interés (rectángulo sobre el Tolima) y bandas de latitud.
- `pipeline/download_firms.py` — descarga hotspots de NASA FIRMS y los agrega a celdas de 0,25° por semana.
- `pipeline/harmonize.py` — calibra MODIS contra VIIRS en el solapamiento (2012+) y exporta `data/harmonized.json`.
- `data/` — datos agregados y resultados (`data/raw/` no se sube).

## Cómo ejecutar el pipeline
1. `pip install -r requirements.txt`
2. Abre `MAP_KEY.txt`, borra el texto y pega tu MAP_KEY de FIRMS (el archivo no se sube al repo).
3. Año de prueba: `python pipeline/download_firms.py --start 2019`
4. Histórico: `python pipeline/download_firms.py --start 2000 --end 2025` (reanuda si se corta)
5. Exportar puntos para la web: `python pipeline/points.py RUTA/A/TOLIMA.gpkg` (municipios del DANE, MGN)
6. (Opcional, versión por celdas) `python pipeline/harmonize.py`
7. Ver la web: `python -m http.server 8765` y abrir http://localhost:8765

## Método
1. Hotspots de FIRMS (`MODIS_SP`, `VIIRS_SNPP_SP`) a resolución nativa, sin duplicados, recortados al Tolima con los límites municipales del DANE.
2. Confianza baja/nominal/alta (MODIS: <30, 30–79, ≥80). Por defecto se usan nominal + alta.
3. Se excluyen los hotspots que FIRMS marca como volcán activo (type 1), fuente fija (type 2) o costa afuera (type 3).
4. Factor de calibración k = ΣVIIRS / ΣMODIS en el solapamiento 2012–2025, por franja de latitud y mes (calculado en la web con los filtros activos).
5. Serie armonizada = MODIS×k antes de 2012 y VIIRS después.
6. Anomalías (z) contra la climatología semanal y detección de periodos críticos.
7. Validación: R² y sesgo en el solapamiento; comparación opcional con cicatrices de quema de Sentinel-2.

## Resultados (nominal + alta, sin fuentes fijas)
- 34.439 hotspots dentro del Tolima (2000–2025); 117 duplicados eliminados.
- k global = 5,91 (norte 6,07 · centro 5,96 · sur 5,74). VIIRS detecta ~6 veces más hotspots que MODIS: predominan quemas pequeñas.
- R² MODIS×k vs VIIRS en bloques de 4 semanas: norte 0,66 · centro 0,85 · sur 0,82 (semanal: 0,43 / 0,69 / 0,63).
- Dos temporadas de quema: enero–marzo y agosto–septiembre (pico climatológico: 27 ago – 2 sep).
- FIRMS marca 731 hotspots de volcán (Villahermosa, Casabianca: Nevado del Ruiz / Cerro Bravo) y 1.489 de fuentes fijas (Ibagué, Espinal, Chaparral).

## Validación externa
Comparación con Perea-Ardila & Murillo-Sandoval, *Tendencia de incendios forestales en el Tolima* (Nota Regional CERE 21, Universidad del Tolima), que usa focos MODIS 2001–2022:

| Indicador (MODIS 2001–2022) | Nota CERE 21 | Este proyecto (todas las confianzas) |
|---|---|---|
| Total de focos | 7.334 | 7.678 (+4,7 %) |
| Año con más focos | 2003 (7,81 %) | 2003 (7,66 %) |
| Segundo año | 2015 (7,15 %) | 2015 (7,14 %) |
| Chaparral, Ortega, Natagaima y Ataco | 24 % | 23,9 % |
| Espinal, Ibagué, San Luis y Rovira | 15,42 % | 15,8 % |

La nota asocia 2003 y 2015 con El Niño. Con el filtro por defecto (nominal + alta, sin fuentes fijas) el grupo de Ibagué baja a 12,6 %, porque se excluyen las fuentes fijas industriales y urbanas de Ibagué y Espinal.

## Créditos de datos
NASA FIRMS (MODIS, VIIRS) · Sentinel-2 cloudless by EOX IT Services GmbH (Contains modified Copernicus Sentinel data 2020) · © OpenStreetMap contributors · DANE, Marco Geoestadístico Nacional.
