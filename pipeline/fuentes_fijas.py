"""Agrupa los hotspots que FIRMS marca como fuente fija (type 2) o volcán (type 1)
y exporta data/fuentes_fijas.json para dibujarlos en el mapa como industrias/volcanes.

Uso:  python pipeline/fuentes_fijas.py
Entrada: data/hotspots.json (de points.py)

Solo se pone nombre a una ubicación cuando hay una fuente pública que la respalde
(ver IDENT). El resto queda como "Fuente fija detectada por FIRMS (sin identificar)".
"""
import json
import math
from pathlib import Path

MIN_N = 10        # mínimo de detecciones para mostrar un grupo
RADIO_KM = 1.5    # radio de agrupación

# Identificaciones verificadas: (lat, lon, radio_km) -> datos
IDENT = [
    {"lat": 4.308, "lon": -75.100, "r": 3, "tipo": "cemento",
     "nombre": "Planta de cemento Caracolito (Payandé)",
     "detalle": "Horno de clínker de la principal planta de cemento del Tolima (Cemex; en venta a Holcim). Su calor constante se detecta como hotspot, pero no es un incendio.",
     "fuente": "https://www.anla.gov.co/01_anla/index.php/noticias/849-este-mecanismo-de-participacion-ciudadana-se-realizo-en-el-corregimiento-payande-tolima-donde-la-multinacional-cemex-opera-la-mina-la-esmeralda-que-produce-materia-prima-para-la-produccion-de-cemento"},
    {"lat": 4.147, "lon": -74.885, "r": 3, "tipo": "molinos",
     "nombre": "Molinos de arroz de El Espinal",
     "detalle": "Los molinos queman la cascarilla del arroz en hornos para secar el grano. Esa combustión continua aparece como hotspot, pero no es un incendio de vegetación.",
     "fuente": "https://repositorio.ucundinamarca.edu.co/bitstreams/54211a2c-7797-4ae5-8f7e-e4fe627e74f3/download"},
]


def km(a, b, c, d):
    return math.hypot((a - c) * 111, (b - d) * 111 * math.cos(math.radians(a)))


def main():
    D = json.loads(Path("data/hotspots.json").read_text(encoding="utf-8"))
    n = D["meta"]["n"]
    names = [m["n"] for m in D["mpios"]]
    out = []
    for t in (2, 1):
        groups = []
        for i in range(n):
            if D["t"][i] != t:
                continue
            la, lo = D["la"][i] / 1e5, D["lo"][i] / 1e5
            for g in groups:
                if km(la, lo, g["la"], g["lo"]) < RADIO_KM:
                    g["p"].append(i)
                    k = len(g["p"])
                    g["la"] += (la - g["la"]) / k
                    g["lo"] += (lo - g["lo"]) / k
                    break
            else:
                groups.append({"la": la, "lo": lo, "p": [i]})
        for g in groups:
            if len(g["p"]) < MIN_N:
                continue
            ys = sorted(2000 + D["y"][i] for i in g["p"])
            mi = max(set(D["m"][i] for i in g["p"]), key=lambda k: sum(D["m"][i] == k for i in g["p"]))
            item = {"lat": round(g["la"], 4), "lon": round(g["lo"], 4), "n": len(g["p"]), "desde": ys[0], "hasta": ys[-1],
                    "municipio": names[mi]}
            if t == 1:
                item.update(tipo="volcan", nombre="Volcán Nevado del Ruiz" if km(g["la"], g["lo"], 4.892, -75.324) < 4 else "Actividad volcánica",
                            detalle="FIRMS marca estos puntos como volcán activo: el calor viene de la actividad volcánica, no de incendios.",
                            fuente="https://www2.sgc.gov.co/volcanes/index.html")
            else:
                for idt in IDENT:
                    if km(g["la"], g["lo"], idt["lat"], idt["lon"]) <= idt["r"]:
                        item.update({k: v for k, v in idt.items() if k not in ("lat", "lon", "r")})
                        break
                else:
                    item.update(tipo="sin_identificar", nombre=f"Fuente fija en {names[mi]}",
                                detalle="FIRMS detecta calor repetido en el mismo lugar durante años (industria, horno u otra fuente fija). Aún no está identificada con una fuente pública.",
                                fuente="")
            out.append(item)
    out.sort(key=lambda x: -x["n"])
    Path("data/fuentes_fijas.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for x in out:
        print(f'{x["n"]:4d}  {x["tipo"]:16s} {x["municipio"]:22s} {x["lat"]},{x["lon"]}  {x["desde"]}-{x["hasta"]}')


if __name__ == "__main__":
    main()
