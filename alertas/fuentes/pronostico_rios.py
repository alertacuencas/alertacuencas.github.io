"""INA: pronóstico de altura por puerto para el Paraná, el Uruguay y el Paraguay.

El INA publica, para unos pocos puertos, un CSV con lo observado y lo pronosticado:
`ina/08-PRONOSTICOS/graficos/<puerto>_prono.csv`. Cada fila trae el valor más probable
("medio" o "main", según el archivo) y un rango ("inferior"–"superior"). El Paraná viene por semana (hoy, +4 días,
+11 días); el Uruguay, día por día. Las fechas son en hora argentina.

Es un archivo publicado, no una API con contrato: si un puerto no responde o trae basura,
ese puerto queda sin pronóstico y los demás siguen. La API a5 (calibrado 289) tiene el
mismo pronóstico del Paraná, pero se actualiza menos seguido que estos archivos.
"""

import csv
import io
import logging
import math
from datetime import date, datetime, timedelta

from alertas.http import pedir
from alertas.tiempo import ART

log = logging.getLogger(__name__)

BASE = "https://alerta.ina.gob.ar/ina/08-PRONOSTICOS/graficos/"
FUENTE = "INA, pronóstico por puerto"
# (puerto, cuenca) como en parana.json → nombre del archivo del INA.
# Quedan afuera Nueva Palmira (Uruguay, el país) y San Fernando (ya tiene el pronóstico horario).
ARCHIVOS = {
    ("Barranqueras", "Paraná"): "barranqueras",
    ("Corrientes", "Paraná"): "corrientes",
    ("Goya", "Paraná"): "goya",
    ("Reconquista", "Paraná"): "reconquista",
    ("La Paz", "Paraná"): "la_paz",
    ("Paraná", "Paraná"): "parana",
    ("Santa Fe", "Paraná"): "santa_fe",
    ("Rosario", "Paraná"): "rosario",
    ("San Javier", "Uruguay"): "san_javier",  # la de Misiones, no la de Santa Fe
    ("Santo Tomé", "Uruguay"): "santo_tome",
    ("Paso de los Libres", "Uruguay"): "paso_de_los_libres",
    ("Formosa", "Paraguay"): "puerto_formosa",
    ("Pilcomayo", "Paraguay"): "puerto_pilcomayo",
}
ALTURA_MIN_M, ALTURA_MAX_M = -5.0, 30.0
# Una corrida al día trae una fila "prono" de hace poco, de hoy o de mañana (el Paraná arranca el
# día de la corrida; el Uruguay, un mes antes; el Paraguay, mañana). Sin eso, la corrida es vieja.
CORRIDA_VIEJA = timedelta(days=3)


def url(archivo: str) -> str:
    return f"{BASE}{archivo}_prono.csv"


def _altura(texto: str | None) -> float | None:
    try:
        v = float(texto or "")
    except ValueError:
        return None
    return round(v, 2) if math.isfinite(v) and ALTURA_MIN_M <= v <= ALTURA_MAX_M else None


def _fecha(texto: str | None) -> date | None:
    try:
        return datetime.fromisoformat(str(texto)).astimezone(ART).date()
    except ValueError:
        return None


def parse_csv(texto: str, ahora: datetime) -> list[dict]:
    """Los días que vienen, con lo más probable y el rango. Vacío si la corrida es vieja."""
    hoy = ahora.astimezone(ART).date()
    filas = [f for f in csv.DictReader(io.StringIO(texto)) if (f.get("tag") or "").strip() == "prono"]
    fechas = [d for f in filas if (d := _fecha(f.get("timestart"))) is not None]
    if not any(-timedelta(days=1) <= hoy - d <= CORRIDA_VIEJA for d in fechas):
        return []
    puntos = []
    for f in filas:
        dia = _fecha(f.get("timestart"))
        medio, inf, sup = (_altura(f.get(k)) for k in ("medio" if "medio" in f else "main", "inferior", "superior"))
        if dia is None or dia <= hoy or None in (medio, inf, sup) or not inf <= medio <= sup:
            continue
        puntos.append({"fecha": dia.isoformat(), "medio": medio, "inferior": inf, "superior": sup})
    return sorted(puntos, key=lambda p: p["fecha"])


def obtener(ahora: datetime) -> dict[tuple[str, str], list[dict]]:
    pronos = {}
    for clave, archivo in ARCHIVOS.items():
        try:
            puntos = parse_csv(pedir(url(archivo)), ahora)
        except Exception as e:  # un puerto caído no tira abajo a los demás
            log.warning("pronóstico de %s: %s", archivo, e)
            continue
        if puntos:
            pronos[clave] = puntos
    return pronos


def agregar(resumen: dict, pronos: dict[tuple[str, str], list[dict]]) -> dict:
    """Copia del resumen de parana.json con el pronóstico en cada puerto que lo tiene."""
    def con_prono(p: dict) -> dict:
        puntos = pronos.get((p.get("puerto"), p.get("cuenca") or "Paraná"))
        return {**p, "pronostico": puntos} if puntos else p

    return {**resumen, "puertos": [con_prono(p) for p in resumen.get("puertos", [])],
            "pronostico": {"fuente": FUENTE, "url": BASE}}
