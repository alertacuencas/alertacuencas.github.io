"""Tiempos del reel a partir de la transcripción de la locución.

Cada bloque del guion arranca en la primera palabra de su texto. Se busca esa palabra (y la
siguiente) en la transcripción con tiempos por palabra; si no aparece, se estima por el largo
del texto. Cada subtítulo arranca cuando la voz dice su primera frase; si no se encuentra,
los subtítulos del bloque se reparten el tramo según el largo de cada uno.
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


def _frases(texto: str) -> list[str]:
    return [f for f in re.split(r"(?<=[.?!])\s+", texto.strip()) if f]


def _inicios_frases(voz: str, palabras: Palabras, a: float, fin: float) -> list[float] | None:
    """Cuándo arranca cada frase de la voz dentro del tramo [a, fin), o None si alguna no aparece."""
    tramo = [(w, s) for w, s in palabras if a - 0.05 <= s < fin]
    normas = [_norm(w) for w, _ in tramo]
    inicios, desde = [a], 1
    for frase in _frases(voz)[1:]:
        i = _buscar(normas, _ancla(frase), desde)
        if i is None:
            return None
        inicios.append(tramo[i][1])
        desde = i + 1
    return inicios


def _subs_bloque(b, palabras: Palabras, a: float, fin: float) -> Subs:
    """Cada subtítulo arranca cuando la voz dice su primera frase. Si las frases de la voz y de los
    subtítulos no se corresponden (o no se encuentran), se reparte el tramo según el largo."""
    cuantas = [len(_frases(s)) for s in b.subs]
    frases = _inicios_frases(b.voz, palabras, a, fin) if sum(cuantas) == len(_frases(b.voz)) else None
    if frases:
        arranques = [frases[sum(cuantas[:i])] for i in range(len(b.subs))]
    else:
        tramo = (fin - a) / (sum(len(s) for s in b.subs) or 1)
        arranques = [a + tramo * sum(len(x) for x in b.subs[:i]) for i in range(len(b.subs))]
    finales = arranques[1:] + [fin]
    return [(round(x, 2), round(z, 2), s) for x, z, s in zip(arranques, finales, b.subs)]


def calcular(g: Guion, palabras: Palabras, duracion: float) -> tuple[dict[str, float], Subs]:
    inicios = _inicios(g, palabras, duracion)
    t = {b.clave: round(s, 2) for b, s in zip(g.bloques, inicios) if b.clave != "hoy"}
    subs: Subs = []
    for k, b in enumerate(g.bloques[:-1]):
        subs.extend(_subs_bloque(b, palabras, inicios[k], inicios[k + 1]))
    if subs:  # el último subtítulo termina justo donde arranca la placa final
        subs[-1] = (subs[-1][0], t["fin"], subs[-1][2])
    return t, subs
