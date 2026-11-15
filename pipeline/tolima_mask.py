"""Recorta la grilla al Tolima usando el GeoPackage de municipios del DANE (MGN).

Uso:   python pipeline/tolima_mask.py RUTA/AL/ARCHIVO.gpkg
Salida: data/tolima.json
  {"municipios":[{"n":nombre,"rings":[[[lon,lat],...],...]}],   (contornos simplificados)
   "cells":[{"r":fila,"c":col,"frac":0..1,"mpio":nombre_dominante}]}  (solo celdas con frac>0)

Sin dependencias extra: lee el GeoPackage con sqlite3 y decodifica el WKB a mano.
frac = fraccion de la celda dentro del Tolima (muestreo de 12x12 puntos).
"""
import json
import sqlite3
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import WEST, NORTH, EAST, SOUTH, STEP  # noqa: E402

NR, NC = round((NORTH - SOUTH) / STEP), round((EAST - WEST) / STEP)
SAMPLES = 12
SIMPLIFY_TOL = 0.004  # grados (~400 m) para el contorno que se dibuja en la web


def parse_gpkg_geom(blob):
    """Devuelve lista de poligonos; cada poligono = lista de anillos [(x,y),...]."""
    flags = blob[3]
    env_len = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}[(flags >> 1) & 7]
    return parse_wkb(memoryview(blob)[8 + env_len:])[0]


def parse_wkb(b, off=0):
    order = "<" if b[off] == 1 else ">"
    gtype = struct.unpack_from(order + "I", b, off + 1)[0] % 1000
    off += 5
    if gtype == 3:  # Polygon
        nrings = struct.unpack_from(order + "I", b, off)[0]
        off += 4
        rings = []
        for _ in range(nrings):
            n = struct.unpack_from(order + "I", b, off)[0]
            off += 4
            pts = struct.unpack_from(order + f"{2 * n}d", b, off)
            off += 16 * n
            rings.append(list(zip(pts[0::2], pts[1::2])))
        return [rings], off
    if gtype == 6:  # MultiPolygon
        n = struct.unpack_from(order + "I", b, off)[0]
        off += 4
        polys = []
        for _ in range(n):
            p, off = parse_wkb(b, off)
            polys += p
        return polys, off
    raise ValueError(f"tipo WKB no soportado: {gtype}")


def point_in_poly(x, y, rings):
    inside = False
    for ring in rings:  # regla par-impar: los huecos restan solos
        j = len(ring) - 1
        for i in range(len(ring)):
            xi, yi = ring[i]
            xj, yj = ring[j]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                inside = not inside
            j = i
    return inside


def simplify(pts, tol):
    """Douglas-Peucker iterativo."""
    if len(pts) < 4:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, z = stack.pop()
        (x1, y1), (x2, y2) = pts[a], pts[z]
        dx, dy = x2 - x1, y2 - y1
        norm = (dx * dx + dy * dy) ** 0.5 or 1e-12
        best, idx = 0.0, -1
        for i in range(a + 1, z):
            d = abs(dy * (pts[i][0] - x1) - dx * (pts[i][1] - y1)) / norm
            if d > best:
                best, idx = d, i
        if best > tol:
            keep[idx] = True
            stack += [(a, idx), (idx, z)]
    return [p for p, k in zip(pts, keep) if k]


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Uso: python pipeline/tolima_mask.py RUTA/AL/ARCHIVO.gpkg")
    con = sqlite3.connect(sys.argv[1])
    table, gcol = con.execute("select table_name, column_name from gpkg_geometry_columns").fetchone()
    mpios = []
    for name, blob in con.execute(f'select mpio_cnmbr, "{gcol}" from "{table}"'):
        polys = parse_gpkg_geom(blob)
        bbox = (min(x for p in polys for r in p for x, _ in r), min(y for p in polys for r in p for _, y in r),
                max(x for p in polys for r in p for x, _ in r), max(y for p in polys for r in p for _, y in r))
        mpios.append({"n": name.title(), "polys": polys, "bbox": bbox})
    print(f"{len(mpios)} municipios leidos de '{table}'")

    cells = []
    for r in range(NR):
        for c in range(NC):
            lat1, lon0 = NORTH - r * STEP, WEST + c * STEP
            hits = {}
            for i in range(SAMPLES):
                for j in range(SAMPLES):
                    x = lon0 + (j + 0.5) * STEP / SAMPLES
                    y = lat1 - (i + 0.5) * STEP / SAMPLES
                    for m in mpios:
                        b = m["bbox"]
                        if b[0] <= x <= b[2] and b[1] <= y <= b[3] and any(point_in_poly(x, y, p) for p in m["polys"]):
                            hits[m["n"]] = hits.get(m["n"], 0) + 1
                            break
            tot = sum(hits.values())
            if tot:
                cells.append({"r": r, "c": c, "frac": round(tot / SAMPLES ** 2, 3),
                              "mpio": max(hits, key=hits.get)})

    out_m = []
    for m in mpios:
        rings = []
        for p in m["polys"]:
            for ring in p[:1]:  # solo anillo exterior para dibujar
                # anillo cerrado: partir en el punto mas lejano del inicio y simplificar cada mitad
                x0, y0 = ring[0]
                k = max(range(len(ring)), key=lambda i: (ring[i][0] - x0) ** 2 + (ring[i][1] - y0) ** 2)
                s = simplify(ring[:k + 1], SIMPLIFY_TOL)[:-1] + simplify(ring[k:], SIMPLIFY_TOL)
                if len(s) >= 4:
                    rings.append([[round(x, 4), round(y, 4)] for x, y in s])
        out_m.append({"n": m["n"], "rings": rings})

    Path("data/tolima.json").write_text(json.dumps({"municipios": out_m, "cells": cells},
                                                   separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    inside = sum(1 for c in cells if c["frac"] >= 0.25)
    print(f"Celdas con algo de Tolima: {len(cells)} de {NR * NC} | con >=25 %: {inside}")
    print(f"Exportado data/tolima.json ({Path('data/tolima.json').stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
