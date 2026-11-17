"""Tiempos del reel a partir de la transcripción de la locución.

Cada bloque del guion arranca en la primera palabra de su texto. Se busca esa palabra (y la
siguiente) en la transcripción con tiempos por palabra; si no aparece, se estima por el largo
del texto. Los subtítulos de cada bloque se reparten su tramo según el largo de cada uno.
"""

import re
import unicodedata

from alertas.reel.guion import Guion

Palabras = list[tuple[str, float]]  # (palabra, segundo en que empieza)
Subs = list[tuple[float, float, str]]


def _norm(palabra: str) -> str:
    sin_tildes = "".join(c for c in unicodedata.normalize("NFD", palabra) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", sin_tildes.lower())


def _ancla(texto: str) -> list[str]:
    return [w for w in (_norm(x) for x in texto.split()) if w][:2]


def _buscar(normas: list[str], ancla: list[str], desde: int) -> int | None:
    for i in range(desde, len(normas) - len(ancla) + 1):
        if normas[i:i + len(ancla)] == ancla:
            return i
    return None


def _inicios(g: Guion, palabras: Palabras, duracion: float) -> list[float]:
    largos = [len(b.voz) + 1 for b in g.bloques]
    total = sum(largos)
    acumulado = [sum(largos[:k]) for k in range(len(largos))]
    normas = [_norm(w) for w, _ in palabras]
    encontrados: list[float | None] = [0.0]
    desde = 0
    palabras_antes = 0
    for k, b in enumerate(g.bloques[1:], start=1):
        # no buscar el comienzo de un bloque dentro del anterior: Whisper junta números
        # ("sesenta y nueve" → "69"), así que se saltea solo la mitad de las palabras previas
        palabras_antes += len(g.bloques[k - 1].voz.split())
        desde = max(desde, palabras_antes // 2)
        i = _buscar(normas, _ancla(b.voz), desde)
        if i is None:
            encontrados.append(None)
        else:
            encontrados.append(palabras[i][1])
            desde = i + 1
    # completar los que faltan interpolando por largo entre los vecinos conocidos
    puntos = [(acumulado[k], t) for k, t in enumerate(encontrados) if t is not None] + [(total, duracion)]
    inicios = []
    for k, t in enumerate(encontrados):
        if t is not None:
            inicios.append(t)
            continue
        (c0, t0), (c1, t1) = next((a, b) for a, b in zip(puntos, puntos[1:]) if a[0] <= acumulado[k] <= b[0])
        inicios.append(round(t0 + (t1 - t0) * (acumulado[k] - c0) / (c1 - c0), 2))
    return inicios


def calcular(g: Guion, palabras: Palabras, duracion: float) -> tuple[dict[str, float], Subs]:
    inicios = _inicios(g, palabras, duracion)
    t = {b.clave: round(s, 2) for b, s in zip(g.bloques, inicios) if b.clave != "hoy"}
    subs: Subs = []
    for k, b in enumerate(g.bloques[:-1]):
        a, fin = inicios[k], inicios[k + 1]
        tramo = (fin - a) / (sum(len(s) for s in b.subs) or 1)
        for s in b.subs:
            z = a + tramo * len(s)
            subs.append((round(a, 2), round(z, 2), s))
            a = z
    if subs:  # el último subtítulo termina justo donde arranca la placa final
        subs[-1] = (subs[-1][0], t["fin"], subs[-1][2])
    return t, subs
