"""Prefectura Naval Argentina: alturas de los ríos del litoral, puerto por puerto.

La página pública de alturas trae, por puerto, la última lectura de la escala, la
variación, el estado y los niveles de alerta y evacuación que fija Prefectura.
Se lee cada 2 a 12 h según el puerto (no es telemetría). Las fechas vienen como
"16/NOV/26 - 1000" en hora argentina.

Se toman los puertos del Paraná (incluido el Delta y San Javier, en Santa Fe), del
Uruguay, del Paraguay, del Río de la Plata y de sus afluentes que tienen niveles de alerta
y evacuación: sin umbral no hay con qué comparar. Cada puerto lleva su "cuenca", el nombre
del río para mostrar (los brazos del Delta cuentan como Paraná).

Respaldo: la página de Prefectura no responde desde fuera de Argentina (los
servidores de GitHub Actions están en EE. UU.). Si falla, se usan las mismas
escalas que el INA republica en su API a5 (red "alturas_prefe"), con una sola
lectura por día, la de las 00 h.
"""

import json
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from html.parser import HTMLParser

from alertas.http import pedir
from alertas.tiempo import ART, a_utc, iso_utc

URL = "https://contenidosweb.prefecturanaval.gob.ar/alturas/"
# Río de la tabla de Prefectura → cuenca, como se nombra en la web y en el reel.
CUENCAS = {
    "PARANA": "Paraná", "DELTA PARANA": "Paraná", "SAN JAVIER": "Paraná", "IBICUY": "Paraná",
    "URUGUAY": "Uruguay", "PARAGUAY": "Paraguay", "DE LA PLATA": "Río de la Plata",
    "IGUAZU": "Iguazú", "GUALEGUAY": "Gualeguay", "GUALEGUAYCHU": "Gualeguaychú",
}
RIOS = frozenset(CUENCAS)
ALTURA_MIN_M = -5.0
ALTURA_MAX_M = 30.0  # escalas del Paraná medio llegan a ~10 m; más que esto es un error
# El INA publica la lectura de las 00 h cerca del mediodía: hasta ~36 h de atraso es normal.
DATO_VIEJO = timedelta(hours=48)
INA_SERIES = "https://alerta.ina.gob.ar/a5/obs/puntual/series?var_id=2&tabla_id=alturas_prefe&format=json"
INA_OBS = "https://alerta.ina.gob.ar/a5/obs/puntual/series/{id}/observaciones?timestart={desde}&timeend={hasta}&format=json"
# Código de río del INA → cuenca, igual que en la tabla de Prefectura (CUENCAS).
CUENCAS_INA = {
    "PARANAMED": "Paraná", "PARANAINF": "Paraná", "SANJAVIER": "Paraná", "BARRANQUERAS": "Paraná",
    "VICTORIA": "Paraná", "PARANADELASPALMAS": "Paraná", "PARANAGUAZU": "Paraná", "PARANAIBICUY": "Paraná",
    "BARADERO": "Paraná", "CANALGAFOTRE": "Paraná", "CHANA": "Paraná", "LUJAN": "Paraná",
    "URUGUAY": "Uruguay", "LATINTA": "Uruguay", "PARAGUAY": "Paraguay", "IGUAZU": "Iguazú",
    "GUALEGUAY": "Gualeguay", "RIODELAPLATA": "Río de la Plata",
}
RIOS_INA = frozenset(CUENCAS_INA)
# Donde el INA y Prefectura no coinciden, manda Prefectura (nombre del puerto y cuenca).
NOMBRES_INA = {"Puerto Pilcomayo": "Pilcomayo", "Puerto Formosa": "Formosa", "Villa Paranacito": "Paranacito"}
CUENCA_POR_PUERTO_INA = {"Gualeguaychú": "Gualeguaychú", "Boca Gualeguaychú": "Gualeguaychú"}
INA_DIAS_ATRAS = 3
# Ubicación de cada escala (lat, lon), tomada del catálogo de estaciones del INA (red
# "alturas_prefe"). La tabla de Prefectura no trae coordenadas.
COORDS = {
    "BELLA VISTA": (-28.5184, -59.0593),
    "BRAZO LARGO": (-33.8833, -58.9),
    "CAMPANA": (-34.1556, -58.9582),
    "CONFLUENCIA": (-25.5927, -54.5934),
    "CORRIENTES": (-27.4636, -58.8389),
    "DIAMANTE": (-32.0716, -60.6432),
    "EL DORADO": (-26.3833, -54.7),
    "ELDORADO": (-26.3833, -54.7),
    "EMPEDRADO": (-27.9541, -58.8185),
    "ESCOBAR": (-34.3, -58.7333),
    "ESQUINA": (-30.0192, -59.5366),
    "GOYA": (-29.1438, -59.273),
    "GUAZUCITO": (-34.0167, -58.4),
    "HERNANDARIAS": (-31.2265, -59.9919),
    "IBICUY": (-33.762, -59.1801),
    "IGUAZU": (-25.5833, -54.5667),
    "ITA IBATE": (-27.4234, -57.3333),
    "ITATI": (-27.2668, -58.2441),
    "ITUZAINGO": (-27.5833, -56.7),
    "LA PAZ": (-30.7342, -59.6381),
    "LIBERTAD": (-25.9167, -54.6211),
    "LIBERTADOR": (-26.8, -55.0333),
    "PARANA": (-31.7182, -60.5226),
    "PASO DE LA PATRIA": (-27.3333, -58.5833),
    "POSADAS": (-27.3667, -55.8833),
    "PUERTO IGUAZU": (-25.5833, -54.5667),
    "PUERTO MANI": (-27.1064, -55.5222),
    "RAMALLO": (-33.4781, -59.9957),
    "RECONQUISTA": (-29.2376, -59.5812),
    "ROSARIO": (-32.9433, -60.6308),
    "SAN LORENZO": (-32.7336, -60.7257),
    "SAN LORENZO (SAN MARTIN)": (-32.7336, -60.7257),
    "SAN NICOLAS": (-33.342, -60.1895),
    "SAN PEDRO": (-33.6745, -59.6497),
    "SANTA ANA": (-27.3351, -55.5884),
    "SANTA ELENA": (-30.95, -59.7833),
    "SANTA FE": (-31.6515, -60.7002),
    "VILLA CONSTITUCION": (-33.2354, -60.3091),
    "YACYRETA AFLUENTE": (-27.4826, -56.7272),
    "YACYRETA EFLUENTE": (-27.4826, -56.7272),
    "ZARATE": (-34.0988, -59.0109),
    "BARRANQUERAS": (-27.4833, -58.9333),
    # el INA ubica esta escala sobre el río Uruguay (otra San Javier, en Misiones): es la
    # de Santa Fe, sobre el río San Javier
    "SAN JAVIER (SANTA FE)": (-30.5833, -59.9333),
    "VICTORIA": (-32.6558, -60.2196),
    "BARADERO": (-33.8007, -59.4956),
    "CANAL NUEVO": (-33.8627, -58.6604),
    "MARTIN GARCIA": (-34.1903, -58.2530),
    "TIGRE": (-34.4159, -58.5780),
    "DIQUE LUJAN": (-34.3516, -58.6861),
    "CHANA MINI": (-34.2, -58.4833),
    "SAN FERNANDO": (-34.4333, -58.55),
    "SAN ISIDRO": (-34.4572, -58.5072),
    "OLIVOS": (-34.5067, -58.4759),
    # Otros ríos (catálogo del INA, salvo los marcados)
    "ANDRESITO": (-25.5833, -53.9833),
    "PUERTO RUIZ": (-33.2167, -59.3667),
    "PILCOMAYO": (-25.3667, -57.65),
    "BOUVIER": (-25.4519, -57.5682),
    "FORMOSA": (-26.1833, -58.1833),
    "BERMEJO": (-26.9263, -58.5062),
    "LAS PALMAS": (-27.0667, -58.6833),  # Las Palmas (Chaco), no está en el catálogo del INA
    "ISLA DEL CERRITO": (-27.3167, -58.6167),
    "EL SOBERBIO": (-27.3, -54.2),
    "ALBA POSSE": (-27.572, -54.6785),
    "PANAMBI": (-27.7306, -54.9131),
    "SAN JAVIER": (-27.8833, -55.1333),  # sobre el Uruguay, en Misiones
    "PUERTO CONCEPCION": (-28.1192, -55.5814),
    "GARRUCHOS": (-28.1833, -55.65),
    "SANTO TOME": (-28.55, -56.0333),
    "ALVEAR": (-29.1, -56.55),
    "LA CRUZ": (-29.1806, -56.634),
    "YAPEYU": (-29.47, -56.8107),
    "PASO DE LOS LIBRES": (-29.7167, -57.0833),
    "BOMPLAND": (-29.8727, -57.3329),
    "MONTE CASEROS": (-30.25, -57.6333),
    "MOCORETA": (-30.7157, -57.8178),
    "FEDERACION": (-30.9932, -57.9147),
    "SALTO GRANDE ABAJO": (-31.2755, -57.9369),
    "CONCORDIA": (-31.4, -58.0167),
    "YERUA": (-31.53, -58.02),  # Puerto Yeruá, no está en el catálogo del INA
    "COLON": (-32.2333, -58.1167),
    "CONCEPCION DEL URUGUAY": (-32.4833, -58.2333),
    "CAMPICHUELO": (-32.701, -58.1834),
    "GUALEGUAYCHU": (-33.0167, -58.5),
    "BOCA GUALEGUAYCHU": (-33.0667, -58.4167),
    "PARANACITO": (-33.72, -58.66),  # Villa Paranacito, no está en el catálogo del INA
    "BUENOS AIRES": (-34.5611, -58.3993),
    "LA PLATA": (-34.8242, -57.8735),
    "ATALAYA": (-35.03, -57.53),  # Magdalena, no está en el catálogo del INA
    "SANTA TERESITA": (-36.54, -56.69),  # no está en el catálogo del INA
}
# Sin ubicación confiable todavía: aparecen en la lista pero no en el mapa.
SIN_UBICACION = frozenset({"LA CALERA", "BRAGA"})
# Orden de la tabla de Prefectura, aguas abajo. En Misiones y Corrientes el río corre de
# este a oeste, así que ordenar por latitud mezclaría los puertos.
ORDEN_RIO = (
    "PUERTO IGUAZU", "LIBERTAD", "EL DORADO", "LIBERTADOR", "PUERTO MANI", "SANTA ANA", "POSADAS",
    "ITUZAINGO", "ITA IBATE", "ITATI", "PASO DE LA PATRIA", "CORRIENTES", "BARRANQUERAS", "EMPEDRADO",
    "BELLA VISTA", "GOYA", "RECONQUISTA", "ESQUINA", "SAN JAVIER (SANTA FE)", "LA PAZ", "SANTA ELENA",
    "HERNANDARIAS", "PARANA", "SANTA FE", "DIAMANTE", "VICTORIA", "SAN LORENZO (SAN MARTIN)", "ROSARIO",
    "VILLA CONSTITUCION", "SAN NICOLAS", "RAMALLO", "SAN PEDRO", "BARADERO", "IBICUY", "GUAZUCITO",
    "ZARATE", "CAMPANA", "ESCOBAR",
)
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
    "IGUAZU": "Iguazú", "PANAMBI": "Panambí", "PUERTO CONCEPCION": "Puerto Concepción",
    "SANTO TOME": "Santo Tomé", "YAPEYU": "Yapeyú", "MOCORETA": "Mocoretá", "FEDERACION": "Federación",
    "YERUA": "Yeruá", "COLON": "Colón", "CONCEPCION DEL URUGUAY": "Concepción del Uruguay",
    "GUALEGUAYCHU": "Gualeguaychú", "BOCA GUALEGUAYCHU": "Boca Gualeguaychú",
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
    lat: float | None = None
    lon: float | None = None
    cuenca: str = "Paraná"


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
    nombre_crudo = _sin_tildes(" ".join(fila.get("Puerto", "").split()))
    return Puerto(
        puerto=_nombre(fila.get("Puerto", "")),
        rio=rio, altura=altura, variacion=variacion, ts=iso_utc(ts),
        alerta=alerta, evacuacion=evacuacion, nivel=_nivel(altura, alerta, evacuacion),
        tendencia=_tendencia(variacion), viejo=ahora - ts > DATO_VIEJO,
        lat=COORDS.get(nombre_crudo, (None, None))[0], lon=COORDS.get(nombre_crudo, (None, None))[1],
        cuenca=CUENCAS[rio],
    )


def parse(html: str, ahora: datetime) -> list[Puerto]:
    """Puertos en el orden de la tabla: cada río de aguas arriba hacia abajo."""
    tabla = _Tabla()
    tabla.feed(html)
    return [p for fila in tabla.filas if (p := _puerto(fila, ahora)) is not None]


@dataclass(frozen=True)
class SerieIna:
    id: int
    puerto: str
    rio: str
    lat: float
    lon: float
    alerta: float
    evacuacion: float
    cuenca: str


def parse_series_ina(texto: str) -> list[SerieIna]:
    """Una serie por puerto con umbrales y datos; cada río de norte a sur."""
    filas = json.loads(texto)
    filas = filas.get("rows", []) if isinstance(filas, dict) else filas
    vistas: dict[str, SerieIna] = {}
    for f in filas:
        e = f.get("estacion") or {}
        try:
            alerta, evac = float(e["nivel_alerta"]), float(e["nivel_evacuacion"])
            lon, lat = float(e["geom"]["coordinates"][0]), float(e["geom"]["coordinates"][1])
        except (KeyError, TypeError, ValueError, IndexError):
            continue
        if e.get("rio") not in RIOS_INA or not e.get("public", True) or not (f.get("date_range") or {}).get("timeend"):
            continue
        nombre = " ".join(str(e.get("nombre", "")).split())
        nombre = NOMBRES_INA.get(nombre, nombre)
        if nombre and nombre not in vistas:  # el INA repite puertos en series auxiliares sin datos
            cuenca = CUENCA_POR_PUERTO_INA.get(nombre, CUENCAS_INA[e["rio"]])
            vistas[nombre] = SerieIna(int(f["id"]), nombre, e["rio"], lat, lon, alerta, evac, cuenca)
    return sorted(vistas.values(), key=_orden)


def _sin_tildes(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().upper()


def _orden(s: "SerieIna") -> tuple[int, float]:
    """Posición en el río; los puertos que no están en la lista van al final, de norte a sur."""
    nombre = _sin_tildes(s.puerto)
    return (ORDEN_RIO.index(nombre) if nombre in ORDEN_RIO else len(ORDEN_RIO), -s.lat)


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
        tendencia=_tendencia(variacion), viejo=ahora - ts > DATO_VIEJO, lat=serie.lat, lon=serie.lon,
        cuenca=serie.cuenca,
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
        raise RuntimeError("el INA no devolvió alturas de los ríos")
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
