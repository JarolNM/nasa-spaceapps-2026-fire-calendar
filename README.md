# NASA Space Apps Challenge 2026 — Harmonizing MODIS and VIIRS Hotspots

**Live app:** https://jarolnm.github.io/nasa-spaceapps-2026-fire-calendar/

Web app that harmonizes MODIS (2000+) and VIIRS S-NPP (2012+) active-fire hotspots into one
burning-activity calendar for an area of interest (pilot: Tolima, Colombia, 2000–2025).

## What the app does
- **Burning calendar** by month, week or day, raw vs. harmonized, absolute vs. anomaly (z).
- **Map** of every hotspot at native resolution (VIIRS 375 m, MODIS 1 km) with confidence classes, municipality search (DANE boundaries), scale bar and north arrow.
- **Fire events:** hotspots grouped into fires (≤ 1.5 km, ≤ 2 days) with severity, thermal footprint, land cover and El Niño/La Niña context. Industrial and persistent heat sources are removed.
- **Before / after** comparison with dated NASA HLS Sentinel-2/Landsat 30 m images.
- **Base maps:** Sentinel-2 yearly (changes every year), NASA HLS image of the day, Esri Wayback, OpenStreetMap, and a **quarterly series 2000–2025** (cloud-free Landsat 5/7/8/9 + Sentinel-2 medians per season, with dNBR burned areas) built with Google Earth Engine.
- **Industries and volcano** layer explaining static false positives (cement kiln, oil flares, rice and coffee mills, Nevado del Ruiz).
- **Sati**, a guide satellite with a neural English voice, and a 7-step animated explainer.

## Structure
- `index.html` — the web app (static site, GitHub Pages).
- `pipeline/download_firms.py` — downloads FIRMS hotspots (needs your own MAP_KEY in `MAP_KEY.txt`, never committed).
- `pipeline/points.py` — merges raw CSVs, removes duplicates, classifies confidence, assigns DANE municipality → `data/hotspots.json`, `data/validation.json`.
- `pipeline/harmonize.py` — calibrates MODIS against VIIRS in the 2012–2025 overlap.
- `pipeline/fuentes_fijas.py` — curated catalog of static heat sources with exact coordinates → `data/fuentes_fijas.json`.
- `pipeline/incendios.py` — groups hotspots into fire events, screens industrial/persistent sources, adds MODIS land cover → `data/incendios.json`.
- `pipeline/trimestral_gee.py` — quarterly (seasonal) composites 2000–2025 with Google Earth Engine → `data/trimestral/`.
- `pipeline/voz_sati.py` — generates Sati's voice (edge-tts, en-US-JennyNeural) → `audio/sati/`.
- `etiquetar.html` — labeling tool for expert review of hotspots (fire / false / unsure).

## Run it
1. `pip install -r requirements.txt`
2. Put your FIRMS MAP_KEY in `MAP_KEY.txt` (git-ignored).
3. `python pipeline/download_firms.py --start 2000 --end 2025` (resumes if interrupted)
4. `python pipeline/points.py PATH/TO/TOLIMA.gpkg` (DANE MGN municipalities)
5. `python pipeline/incendios.py`
6. Optional: `earthengine authenticate` then `python pipeline/trimestral_gee.py --project YOUR-GCP-PROJECT [--drive]`
7. `python -m http.server 8765` and open http://localhost:8765

## Method
1. FIRMS standard archives (`MODIS_SP` C6.1, `VIIRS_SNPP_SP`) at native resolution, de-duplicated, clipped to Tolima with DANE municipal boundaries.
2. Confidence low/nominal/high (MODIS: <30, 30–79, ≥80); nominal + high by default.
3. False positives: FIRMS type 1–3 removed; for fire events also a radius around 20 catalogued static sources (volcano 5 km, cement/oil 1.5 km, mills 1 km) and persistent thermal anomalies (same ~450 m cell on ≥ 4 years and ≥ 8 days). 588 hotspots removed.
4. Calibration factor k = ΣVIIRS / ΣMODIS over 2012–2025 per latitude band and month (computed live with the active filters).
5. Harmonized series = MODIS×k before 2012, VIIRS after.
6. Anomalies (z) against each era's weekly climatology; critical periods with z ≥ 1.5.
7. Quarterly composites: cloud/shadow masking (Landsat QA_PIXEL, Sentinel-2 Cloud Score+), sensor harmonization to Landsat 8 OLI (Roy et al. 2016; HLS coefficients), seasonal median, NDVI, NBR and dNBR.

## Results (nominal + high, no static sources)
- 34,439 hotspots inside Tolima (2000–2025); 117 duplicates removed.
- Global k = 5.91 (north 6.07 · center 5.96 · south 5.74): VIIRS detects ~6× more hotspots than MODIS.
- R² MODIS×k vs. VIIRS in 4-week blocks: north 0.66 · center 0.85 · south 0.82.
- Two burning seasons: January–March and August–September (climatological peak: 27 Aug – 2 Sep).
- 17,583 fire events (5,523 with ≥ 2 detections); largest: San Luis, Aug 2015 (1,945 MW) and Natagaima, Sep 2024 (99 detections, ~1,022 ha).

## External validation
Compared with Perea-Ardila & Murillo-Sandoval, *Forest fire trends in Tolima* (CERE Regional Note 21, University of Tolima), MODIS 2001–2022:

| Indicator (MODIS 2001–2022) | CERE Note 21 | This project (all confidences) |
|---|---|---|
| Total hotspots | 7,334 | 7,678 (+4.7 %) |
| Peak year | 2003 (7.81 %) | 2003 (7.66 %) |
| Second year | 2015 (7.15 %) | 2015 (7.14 %) |
| Chaparral, Ortega, Natagaima, Ataco | 24 % | 23.9 % |
| Espinal, Ibagué, San Luis, Rovira | 15.42 % | 15.8 % |

## References
1. NASA FIRMS, LANCE/EOSDIS — https://firms.modaps.eosdis.nasa.gov/
2. Giglio, L., Schroeder, W., Justice, C.O. (2016). The collection 6 MODIS active fire detection algorithm and fire products. *Remote Sens. Environ.* 178, 31–41. doi:10.1016/j.rse.2016.02.054
3. Schroeder, W., Oliva, P., Giglio, L., Csiszar, I.A. (2014). The New VIIRS 375 m active fire detection data product. *Remote Sens. Environ.* 143, 85–96. doi:10.1016/j.rse.2013.12.008
4. Liu, T., et al. (2019). Missing emissions from post-monsoon agricultural fires in northwestern India. *Environ. Res. Commun.* 1, 011007. doi:10.1088/2515-7620/ab056c
5. Key, C.H., Benson, N.C. (2006). Landscape Assessment (dNBR). USDA Forest Service RMRS-GTR-164-CD.
6. Claverie, M., et al. (2018). The Harmonized Landsat and Sentinel-2 surface reflectance data set. *Remote Sens. Environ.* 219, 145–161. doi:10.1016/j.rse.2018.09.002
7. Roy, D.P., et al. (2016). Characterization of Landsat-7 to Landsat-8 reflective wavelength and NDVI continuity. *Remote Sens. Environ.* 185, 57–70. doi:10.1016/j.rse.2015.12.024
8. Gorelick, N., et al. (2017). Google Earth Engine: Planetary-scale geospatial analysis for everyone. *Remote Sens. Environ.* 202, 18–27. doi:10.1016/j.rse.2017.06.031
9. Pasquarella, V.J., et al. (2023). Cloud Score+. *CVPR Workshops*.
10. Friedl, M., Sulla-Menashe, D. (2019). MCD12Q1 v006 land cover. NASA LP DAAC. doi:10.5067/MODIS/MCD12Q1.006
11. NOAA CPC — Oceanic Niño Index (ONI).
12. DANE — Marco Geoestadístico Nacional; IDEAM — Colombian climate atlas; Servicio Geológico Colombiano.
13. Perea-Ardila, M.A., Murillo-Sandoval, P.J. CERE Regional Note 21, University of Tolima.
14. Sentinel-2 cloudless © EOX IT Services GmbH (CC BY-NC-SA 4.0); Esri World Imagery Wayback; © OpenStreetMap contributors.

### Burn severity and spectral indices
19. Rouse, J.W., Haas, R.H., Schell, J.A., Deering, D.W. (1973). Monitoring vegetation systems in the Great Plains with ERTS. Third ERTS Symposium, NASA SP-351 I, 309–317 — NDVI.
20. López-García, M.J., Caselles, V. (1991). Mapping burns and natural reforestation using Thematic Mapper data. Geocarto International 6(1), 31–37 — NBR. doi:10.1080/10106049109354290
21. Parks, S.A., Dillon, G.K., Miller, C. (2014). A new metric for quantifying burn severity: the Relativized Burn Ratio. Remote Sensing 6(3), 1827–1844. doi:10.3390/rs6031827
22. Parks, S.A., Holsinger, L.M., Voss, M.A., Loehman, R.A., Robinson, N.P. (2018). Mean composite fire severity metrics computed with Google Earth Engine offer improved accuracy and expanded mapping potential. Remote Sensing 10(6), 879. doi:10.3390/rs10060879
23. Saulino, L., Rita, A., Migliozzi, A., Maffei, C., Allevato, E., Garonna, A.P., Saracino, A. (2020). Detecting burn severity across Mediterranean forest types by coupling medium-spatial resolution satellite imagery and field data. Remote Sensing 12(4), 741. doi:10.3390/rs12040741
24. van Gerrevink, M.J., Veraverbeke, S. (2021). Evaluating the hyperspectral sensitivity of the differenced Normalized Burn Ratio for assessing fire severity. Remote Sensing 13(22), 4611. doi:10.3390/rs13224611
25. Smichowski, H., Contreras, F.I. (2024). Application of Google Earth Engine in the preliminary analysis of fire severity in the Iberá National Park and Reserve, Argentina. Rev. U.D.C.A Act. & Div. Cient. 27(1), e2464. doi:10.31910/rudca.v27.n1.2024.2464
26. He, K., Shen, X., Anagnostou, E.N. (2024). A global forest burn severity dataset from Landsat imagery (2003–2016). Earth System Science Data 16(6), 3061–3081. doi:10.5194/essd-16-3061-2024
27. Ghazali, N.N., Saraf, N.M., Rasam, A.R.A., Othman, A.N., Salleh, S.A., Saad, N.M. (2025). Forest fire severity level using dNBR spectral index. Revue Internationale de Géomatique 34(1), 89–101. doi:10.32604/rig.2025.057562
28. Han, L., Liu, Y., Wang, Q., Long, T., Lu, N., Wang, L., Xu, W. (2026). An improved framework for forest fire severity assessment in mountainous areas based on the dNBR index: a case study from central Yunnan, China. Remote Sensing 18(8), 1118. doi:10.3390/rs18081118
29. UN-SPIDER. Normalized Burn Ratio (NBR) — recommended practice for burn severity. Accessed 6 Oct 2026. un-spider.org
30. Geodesta. Google Earth Engine. Accessed 6 Oct 2026. geodesta.com
31. GIS&Beers. Análisis de severidad de incendios NBR en Google Earth Engine. Accessed 6 Oct 2026. gisandbeers.com
32. GIS&Beers. Análisis de la severidad de incendios a través del índice NBR. Accessed 6 Oct 2026. gisandbeers.com

## Use of AI (SI) tools
- **Assistant:** Anthropic Claude, used under the direction of the GeoElectronic team; all results were reviewed and tested by the team.
- **Images / animation:** the Sati mascot, intro and 7-step explainer are AI-assisted SVG and carry a visible "✦ AI-generated" watermark. Satellite imagery is real (Landsat, Sentinel-2, NASA HLS, Esri), not AI-generated.
- **Audio:** Sati's voice is AI-generated speech (Microsoft neural TTS en-US-JennyNeural via edge-tts); every MP3 has an ID3 disclosure (see `audio/sati/ABOUT.md`).
- **Code:** `index.html`, `etiquetar.html` and `pipeline/*.py` are AI-assisted; each has a header comment or `meta name="ai-assistance"` tag.
- **Data:** observations are real and unmodified (NASA FIRMS, USGS/NASA, Copernicus, NOAA, DANE); derived JSON files carry `"ai_assisted": true` in their metadata.
- No NASA logos, insignia, flags or mission identifiers were generated or modified.
