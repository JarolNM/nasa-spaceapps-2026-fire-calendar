# Pitch script — ~3 min

> All numbers computed from real data (nominal + high confidence, static sources removed).

## 1. Problem (30 s)
- Satellites have detected active fires since 2000, but the record is split in two:
  **MODIS** (1 km, since 2000) and **VIIRS** (375 m, since 2012).
- VIIRS sees smaller fires, so it detects **~6× more hotspots** at the same place and week.
- Gluing both series together creates a fake "fire increase" in 2012 that is really
  **a sensor change**. That misleads anyone looking for trends or anomalous periods.

## 2. Our solution (45 s)
- A **burning-activity calendar** (year × month/week/day) for **Tolima, Colombia**, 2000–2025.
- Harmonization: in the overlap years (2012–2025) we compute **k = Σ VIIRS / Σ MODIS** per
  **latitude band** and **month**, and rescale MODIS before 2012 → one continuous 26-year series in "VIIRS units".
- Cleaning: we remove the volcano, a cement kiln, oil flares and rice/coffee mills (588 hotspots), using a
  curated catalog plus a persistent-heat test.

## 3. Demo (60 s)
1. Raw vs. harmonized calendar: the 2012 jump disappears.
2. "Was it normal?" anomaly view: El Niño years (2015, 2024) light up.
3. Fire events: Natagaima, 12–22 Sep 2024 — 99 detections, 11.4 km east of town, ~1,022 ha of savanna, very high severity.
4. Before / after with Sentinel-2: green on 4 Sep → burn scar on 24 Sep.
5. Quarterly 2000–2025 base map: cloud-free seasonal composites with dNBR burned areas.

## 4. Validation (20 s)
- MODIS×k reproduces VIIRS with **R² = 0.66 / 0.85 / 0.82** (north/center/south, 4-week blocks); k = 5.91.
- **External:** matches University of Tolima CERE Note 21 — same peak years (2003, 2015), same municipal shares (24 % Chaparral, Ortega, Natagaima, Ataco), total within 5 %.

## 5. Limitations (15 s)
- A hotspot is not a burned hectare: we measure **detection activity**; footprints are upper estimates.
- Clouds and overpass time affect detections; k is assumed constant in time.
- Only VIIRS S-NPP (NOAA-20/21 would create artificial jumps).

## 6. Future work (10 s)
- Any region of the world (only `config.py` changes).
- NOAA-20/21, MCD64A1 burned area, drought indices; automatic weekly alerts when z ≥ 1.5.

## Who it is for
Early warning and emergency response (firefighters, CORTOLIMA, UNGRD), scientists and land managers.
