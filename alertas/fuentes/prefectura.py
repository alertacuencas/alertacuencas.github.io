"""Prefectura Naval Argentina: alturas del río Paraná, puerto por puerto.

La página pública de alturas trae, por puerto, la última lectura de la escala, la
variación, el estado y los niveles de alerta y evacuación que fija Prefectura.
Se lee cada 2 a 12 h según el puerto (no es telemetría). Las fechas vienen como
"16/NOV/26 - 1000" en hora argentina.

Solo se toman los puertos del Paraná (incluido el Delta y San Javier, en Santa Fe)
que tienen niveles de alerta y evacuación: sin umbral no hay con qué comparar.

Respaldo: la página de Prefectura no responde desde fuera de Argentina (los
servidores de GitHub Actions están en EE. UU.). Si falla, se usan las mismas
escalas que el INA republica en su API a5 (red "alturas_prefe"), con una sola
lectura por día, la de las 00 h.
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from html.parser import HTMLParser

from alertas.http import pedir
from alertas.tiempo import ART, a_utc, iso_utc

URL = "https://contenidosweb.prefecturanaval.gob.ar/alturas/"
RIOS = frozenset({"PARANA", "DELTA PARANA", "SAN JAVIER"})
ALTURA_MIN_M = -5.0
ALTURA_MAX_M = 30.0  # escalas del Paraná medio llegan a ~10 m; más que esto es un error
# El INA publica la lectura de las 00 h cerca del mediodía: hasta ~36 h de atraso es normal.
DATO_VIEJO = timedelta(hours=48)
INA_SERIES = "https://alerta.ina.gob.ar/a5/obs/puntual/series?var_id=2&tabla_id=alturas_prefe&format=json"
INA_OBS = "https://alerta.ina.gob.ar/a5/obs/puntual/series/{id}/observaciones?timestart={desde}&timeend={hasta}&format=json"
# Códigos de río del INA para el Paraná y sus brazos del Delta.
RIOS_INA = frozenset({"PARANAMED", "PARANAINF", "SANJAVIER", "PARANADELASPALMAS", "PARANAGUAZU", "PARANAIBICUY"})
INA_DIAS_ATRAS = 3
UMBRAL_ESTABLE_M = 0.02
MESES = {"ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6,
         "JUL": 7, "AGO": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DIC": 12}
VERSION = 1
# La tabla viene en mayúsculas y sin tildes.
NOMBRES = {
    "PARANA": "Paraná", "ITUZAINGO": "Ituzaingó", "ITA IBATE": "Itá Ibaté", "ITATI": "Itatí",
    "SAN NICOLAS": "San Nicolás", "VILLA CONSTITUCION": "Villa Constitución", "ZARATE": "Zárate",
    "DIQUE LUJAN": "Dique Luján", "CHANA MINI": "Chaná Miní", "MARTIN GARCIA": "Martín García",
    "GUAZUCITO": "Guazucito", "PUERTO MANI": "Puerto Maní",
}


@dataclass(frozen=True)
class Puerto:
    puerto: str
    rio: str
    altura: float
    variacion: float | None
    ts: str
    alerta: float
    evacuacion: float
    nivel: str      # "evacuacion" | "alerta" | "normal"
    tendencia: str  # "sube" | "baja" | "estable" | "sin_dato"
    viejo: bool


class _Tabla(HTMLParser):
    """Junta cada fila como {data-label: texto}. Cada celda trae su etiqueta en data-label."""

    def __init__(self) -> None:
        super().__init__()
        self.filas: list[dict[str, str]] = []
        self._fila: dict[str, str] | None = None
        self._etiqueta: str | None = None

    def handle_starttag(self, tag, attrs):  # noqa: ANN001
        if tag == "tr":
            self._fila = {}
        elif tag in ("td", "th") and self._fila is not None:
            label = dict(attrs).get("data-label")
            self._etiqueta = label.rstrip(":").strip() if label else None
            if self._etiqueta:
                self._fila[self._etiqueta] = ""

    def handle_endtag(self, tag):  # noqa: ANN001
        if tag in ("td", "th"):
            self._etiqueta = None
        elif tag == "tr" and self._fila is not None:
            if self._fila:
                self.filas.append(self._fila)
            self._fila = None

    def handle_data(self, data):  # noqa: ANN001
        if self._fila is not None and self._etiqueta:
            self._fila[self._etiqueta] += data


def _numero(texto: str | None) -> float | None:
    try:
        return float((texto or "").strip())
    except ValueError:
        return None  # "S/E", "-" o vacío


def parse_fecha(texto: str) -> datetime:
    """'16/NOV/26 - 1000' (hora argentina) → datetime UTC."""
    fecha, hora = (p.strip() for p in texto.split("-"))
    dia, mes, anio = fecha.split("/")
    local = datetime(2000 + int(anio), MESES[mes.upper()], int(dia), int(hora[:2]), int(hora[2:4]))
    return a_utc(local, ART)


_MENORES = {"de", "del", "la", "las", "los", "el"}


def _nombre(texto: str) -> str:
    crudo = " ".join(texto.split()).upper()
    if crudo in NOMBRES:
        return NOMBRES[crudo]
    palabras = crudo.title().split()
    return " ".join(w.lower() if i and w.lower() in _MENORES else w for i, w in enumerate(palabras))


def _nivel(altura: float, alerta: float, evacuacion: float) -> str:
    if altura >= evacuacion:
        return "evacuacion"
    if altura >= alerta:
        return "alerta"
    return "normal"


def _tendencia(variacion: float | None) -> str:
    if variacion is None:
        return "sin_dato"
    if abs(variacion) < UMBRAL_ESTABLE_M:
        return "estable"
    return "sube" if variacion > 0 else "baja"


def _puerto(fila: dict[str, str], ahora: datetime) -> Puerto | None:
    rio = " ".join(fila.get("Río", "").split()).upper()
    if rio not in RIOS:
        return None
    altura = _numero(fila.get("Ultimo Registro"))
    alerta, evacuacion = _numero(fila.get("Alerta")), _numero(fila.get("Evacuación"))
    if altura is None or alerta is None or evacuacion is None:
        return None
    if not ALTURA_MIN_M <= altura <= ALTURA_MAX_M:
        return None
    try:
        ts = parse_fecha(fila.get("Fecha Hora", ""))
    except (ValueError, KeyError, IndexError):
        return None
    variacion = _numero(fila.get("Variacion"))
    return Puerto(
        puerto=_nombre(fila.get("Puerto", "")),
        rio=rio, altura=altura, variacion=variacion, ts=iso_utc(ts),
        alerta=alerta, evacuacion=evacuacion, nivel=_nivel(altura, alerta, evacuacion),
        tendencia=_tendencia(variacion), viejo=ahora - ts > DATO_VIEJO,
    )


def parse(html: str, ahora: datetime) -> list[Puerto]:
    """Puertos del Paraná en el orden de la tabla (de aguas arriba hacia el Delta)."""
    tabla = _Tabla()
    tabla.feed(html)
    return [p for fila in tabla.filas if (p := _puerto(fila, ahora)) is not None]


@dataclass(frozen=True)
class SerieIna:
    id: int
    puerto: str
    rio: str
    lat: float
    alerta: float
    evacuacion: float


def parse_series_ina(texto: str) -> list[SerieIna]:
    """Una serie por puerto del Paraná con umbrales y datos; de norte a sur."""
    filas = json.loads(texto)
    filas = filas.get("rows", []) if isinstance(filas, dict) else filas
    vistas: dict[str, SerieIna] = {}
    for f in filas:
        e = f.get("estacion") or {}
        try:
            alerta, evac = float(e["nivel_alerta"]), float(e["nivel_evacuacion"])
            lat = float(e["geom"]["coordinates"][1])
        except (KeyError, TypeError, ValueError, IndexError):
            continue
        if e.get("rio") not in RIOS_INA or not e.get("public", True) or not (f.get("date_range") or {}).get("timeend"):
            continue
        nombre = " ".join(str(e.get("nombre", "")).split())
        if nombre and nombre not in vistas:  # el INA repite puertos en series auxiliares sin datos
            vistas[nombre] = SerieIna(int(f["id"]), nombre, e["rio"], lat, alerta, evac)
    return sorted(vistas.values(), key=lambda s: -s.lat)


def parse_obs_ina(texto: str) -> list[tuple[datetime, float]]:
    obs = []
    for o in json.loads(texto) or []:
        valor = _numero(str(o.get("valor")))
        try:
            ts = a_utc(datetime.fromisoformat(str(o["timestart"]).replace("Z", "+00:00")))
        except (KeyError, ValueError):
            continue
        if valor is not None and ALTURA_MIN_M <= valor <= ALTURA_MAX_M:
            obs.append((ts, valor))
    return sorted(obs)


def puerto_ina(serie: SerieIna, obs: list[tuple[datetime, float]], ahora: datetime) -> Puerto | None:
    if not obs:
        return None
    ts, altura = obs[-1]
    variacion = round(altura - obs[-2][1], 2) if len(obs) > 1 else None
    return Puerto(
        puerto=serie.puerto, rio=serie.rio, altura=altura, variacion=variacion, ts=iso_utc(ts),
        alerta=serie.alerta, evacuacion=serie.evacuacion, nivel=_nivel(altura, serie.alerta, serie.evacuacion),
        tendencia=_tendencia(variacion), viejo=ahora - ts > DATO_VIEJO,
    )


def obtener_ina(ahora: datetime) -> list[Puerto]:
    desde, hasta = iso_utc(ahora - timedelta(days=INA_DIAS_ATRAS)), iso_utc(ahora)
    puertos = []
    for serie in parse_series_ina(pedir(INA_SERIES)):
        try:
            obs = parse_obs_ina(pedir(INA_OBS.format(id=serie.id, desde=desde, hasta=hasta)))
        except Exception:  # un puerto caído no tira abajo a los demás
            continue
        if (p := puerto_ina(serie, obs, ahora)) is not None:
            puertos.append(p)
    if not puertos:
        raise RuntimeError("el INA no devolvió alturas del Paraná")
    return puertos


FUENTES = {
    "prefectura": ("Prefectura Naval Argentina", URL),
    "ina": ("Prefectura Naval Argentina, vía INA (lectura diaria)", "https://alerta.ina.gob.ar/a5/"),
}


def resumen(puertos: list[Puerto], ahora: datetime, via: str = "prefectura") -> dict:
    vigentes = [p for p in puertos if not p.viejo]
    fuente, url = FUENTES[via]
    return {
        "version": VERSION,
        "generado": ahora.isoformat(),
        "fuente": fuente,
        "via": via,
        "url": url,
        "evacuacion": [p.puerto for p in vigentes if p.nivel == "evacuacion"],
        "alerta": [p.puerto for p in vigentes if p.nivel == "alerta"],
        "puertos": [asdict(p) for p in puertos],
    }


def obtener(ahora: datetime) -> list[Puerto]:
    return parse(pedir(URL), ahora)


def obtener_con_respaldo(ahora: datetime) -> tuple[list[Puerto], str]:
    """Prefectura directo; si no responde o viene vacía, las mismas escalas vía INA."""
    try:
        puertos = obtener(ahora)
        if puertos:
            return puertos, "prefectura"
    except Exception:  # noqa: BLE001 - se informa abajo si también falla el INA
        pass
    return obtener_ina(ahora), "ina"
