# AI-assisted code: written with Anthropic Claude under the direction of the GeoElectronic team, reviewed and tested by the team.
"""Area de interes (AOI) compartida por download_firms.py y harmonize.py.

Piloto: departamento del Tolima (Colombia). Es un rectangulo que lo contiene con un
pequeño margen, alineado a la grilla de 0,25 grados; incluye partes de departamentos
vecinos (Huila, Cundinamarca, Quindio, Risaralda, Caldas, Valle). Para recortar solo
al Tolima, usa data/urban_mask.csv (row,col) o un poligono en un paso posterior.
"""
WEST, SOUTH, EAST, NORTH = -76.25, 2.75, -74.25, 5.5
STEP = 0.25

# Bandas de latitud para calibrar k: (limite norte-centro, limite centro-sur)
BAND_CUTS = (4.5, 3.75)
BAND_NAMES = ("norte", "centro", "sur")
