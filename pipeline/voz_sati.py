"""Genera la voz natural de Sati (MP3) a partir de audio/sati/textos.json.

Uso:  pip install edge-tts
      python pipeline/voz_sati.py [voz]      (por defecto es-CO-SalomeNeural; otra: es-CO-GonzaloNeural)

Cada archivo se llama como el hash djb2 (base 36) del texto, igual que hashTxt() en index.html.
Los textos se recolectan recorriendo la página (años, municipios, botones, industrias y la
explicación animada) con los filtros por defecto; si un texto no tiene audio, la web usa la voz del navegador.
"""
import asyncio
import json
import os
import struct
import sys

import edge_tts

VOZ = sys.argv[1] if len(sys.argv) > 1 else "es-CO-SalomeNeural"
DIR = "audio/sati"


def h36(t):
    h = 5381
    b = t.encode("utf-16-le")
    for i in range(0, len(b), 2):
        h = ((h << 5) + h + struct.unpack("<H", b[i:i + 2])[0]) & 0xFFFFFFFF
    d, s = "0123456789abcdefghijklmnopqrstuvwxyz", ""
    while True:
        s = d[h % 36] + s
        h //= 36
        if not h:
            return s


async def main():
    textos = json.load(open(f"{DIR}/textos.json", encoding="utf-8"))
    sem, hechos = asyncio.Semaphore(4), []

    async def uno(t):
        k = h36(t)
        async with sem:
            await edge_tts.Communicate(t, VOZ, rate="+4%", pitch="+3Hz").save(f"{DIR}/{k}.mp3")
            hechos.append(k)

    await asyncio.gather(*[uno(t) for t in textos])
    json.dump(sorted(set(hechos)), open(f"{DIR}/index.json", "w"))
    print(len(hechos), "audios generados con", VOZ)


if __name__ == "__main__":
    asyncio.run(main())
