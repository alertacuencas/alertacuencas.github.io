"""Guion del reel diario a partir del estado del día.

Función pura: recibe los JSON que arma el poll y devuelve el texto para la voz de ElevenLabs
(números en letras, frases cortas con comas para las pausas), los subtítulos (con cifras),
la ciudad de ejemplo, el texto del posteo y el titular de la portada. Las reglas de estilo
están en reels/README.md.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from alertas.publicar import resumen
from alertas.reel.numeros import distancia_sub, distancia_voz, en_letras
from alertas.tiempo import ART

URL = "alertacuencas.github.io"
MAX_SUB = 52            # caracteres por subtítulo antes de partirlo
UMBRAL_SUDESTADA = 0.5  # m sobre la marea en San Fernando para mencionarlo
MAX_EDAD_RESIDUO = timedelta(hours=6)
MAX_PEORES = 4          # ciudades en evacuación que se nombran con su número
SMN_GRAVEDAD = resumen.SMN_GRAVEDAD
SMN_TXT = resumen.SMN_TXT


@dataclass(frozen=True)
class Bloque:
    clave: str             # hoy | costa | tuCiudad | ciudad | rio | noOficial | fin
    voz: str               # lo que lee Julieta
    subs: tuple[str, ...]  # subtítulos de este tramo (vacío en la placa final)


@dataclass(frozen=True)
class Guion:
    fecha: datetime        # hora argentina
    ciudad: str            # nombre exacto del puerto, para buscarlo en la web
    bloques: tuple[Bloque, ...]
    posteo: str
    titular_portada: str
    nivel_parana: str
    costa_nivel: str       # vacío si el reel no habla de la costa
    avisos: tuple[str, ...]  # cosas a revisar antes de grabar
    fichas: tuple[str, ...] = ()  # puertos que nombra el bloque "ciudad", en orden: una ficha por frase

    @property
    def texto_voz(self) -> str:
        return " ".join(b.voz for b in self.bloques)


def cargar(ruta) -> Guion:
    """Lee un guion guardado con salida.guardar_guion (el armado usa el mismo texto que leyó la voz)."""
    import json
    from pathlib import Path

    d = json.loads(Path(ruta).read_text(encoding="utf-8"))
    return Guion(
        fecha=datetime.fromisoformat(d["fecha"]), ciudad=d["ciudad"],
        bloques=tuple(Bloque(b["clave"], b["voz"], tuple(b["subs"])) for b in d["bloques"]),
        posteo=d["posteo"], titular_portada=d["titular_portada"], nivel_parana=d["nivel_parana"],
        costa_nivel=d["costa_nivel"], avisos=tuple(d["avisos"]),
        fichas=tuple(d.get("fichas") or ((d["ciudad"],) if d["ciudad"] else ())),
    )


# ---------- helpers ----------

def _nombre_voz(puerto: str) -> str:
    nombre = _nombre_sub(puerto)
    return "la ciudad de Paraná" if nombre == "Paraná" else nombre


def _nombre_sub(puerto: str) -> str:
    return re.sub(r"\s*\(.*?\)", "", puerto).strip()


def _partir(texto: str) -> tuple[str, ...]:
    """Corta un texto en subtítulos: por oración, juntando las cortas, sin punto final."""
    oraciones = [o.strip() for o in re.split(r"(?<=[.?!])\s+", texto) if o.strip()]
    trozos: list[str] = []
    for o in oraciones:
        if trozos and len(trozos[-1]) + 1 + len(o) <= MAX_SUB:
            trozos[-1] = f"{trozos[-1]} {o}"
        else:
            trozos.append(o)
    return tuple(t[:-1] if t.endswith(".") else t for t in trozos)


def _vigentes(estado: dict | None, ahora: datetime) -> tuple[str, str]:
    """El nivel SMN más grave entre las alertas que todavía no vencieron, y su evento."""
    mejor = None
    for z in (estado or {}).get("zonas", {}).values():
        for a in z.get("alertas", []):
            expira = a.get("expira")
            if expira and datetime.fromisoformat(expira) <= ahora:
                continue
            if mejor is None or SMN_GRAVEDAD.get(a["nivel"], 9) < SMN_GRAVEDAD.get(mejor["nivel"], 9):
                mejor = a
    return (mejor["nivel"], mejor["evento"].lower()) if mejor else ("verde", "")


def _por_nombre(parana: dict | None) -> dict[str, dict]:
    return {p["puerto"]: p for p in (parana or {}).get("puertos", []) if not p.get("viejo")}


# ---------- bloques ----------

def _hoy(evac_: list[str], alerta_: list[str], nivel: str) -> tuple[str, str]:
    """Devuelve (voz, subtítulo con cifras)."""
    voz = _hoy_texto([_nombre_voz(n) for n in evac_], [_nombre_voz(n) for n in alerta_], nivel)[0]
    return voz, _hoy_texto([_nombre_sub(n) for n in evac_], [_nombre_sub(n) for n in alerta_], nivel)[1]


def _hoy_texto(evac: list[str], alerta: list[str], nivel: str) -> tuple[str, str]:
    if evac:
        n = len(evac)
        if n == 1:
            return (f"Hoy, una ciudad del Paraná está en evacuación: {evac[0]}.",) * 2
        return (f"Hoy, {en_letras(n, femenino=True)} ciudades del Paraná están en evacuación.",
                f"Hoy, {n} ciudades del Paraná están en evacuación.")
    if alerta:
        m = len(alerta)
        if m == 1:
            voz = sub = f"Hoy, el Paraná está en alerta en {alerta[0]}."
        else:
            voz = f"Hoy, {en_letras(m, femenino=True)} ciudades del Paraná están en alerta. Desde {alerta[0]} hasta {alerta[-1]}."
            sub = f"Hoy, {m} ciudades del Paraná están en alerta. Desde {alerta[0]} hasta {alerta[-1]}."
        return voz, sub
    if nivel == "normal":
        voz = "Hoy, el Paraná está normal en todos los puertos."
    else:
        voz = "Hoy, no hay lecturas recientes del Paraná."
    return voz, voz


def _residuo_reciente(serie: dict | None, ahora: datetime) -> float | None:
    """Último residuo de San Fernando (m sobre la marea), si es de las últimas horas."""
    residuos = ((serie or {}).get("estaciones", {}).get("SFER", {}) or {}).get("residuo") or []
    if not residuos:
        return None
    ts, valor = residuos[-1]
    if valor is None or ahora - datetime.fromisoformat(ts) > MAX_EDAD_RESIDUO:
        return None
    return valor


def _costa(parana: dict | None, serie: dict | None, smn: tuple[str, str], ahora: datetime) -> tuple[str, str, str, str]:
    """Devuelve (nivel, voz, subtítulo, frase para el titular). Nivel "sin" si no hay datos."""
    nivel, _ = resumen._costa(parana, serie)
    residuo = _residuo_reciente(serie, ahora)
    if nivel in ("evacuacion", "alerta"):
        fuera = [p["puerto"] for p in sorted(_por_nombre(parana).values(), key=resumen._gravedad)
                 if p.get("rio") in resumen.RIOS_DELTA and p["nivel"] != "normal"]
        verbo = "está" if len(fuera) == 1 else "están"
        estado = f"{verbo} en {resumen.NIVEL_TXT[nivel]}."
        voz = f"En el Delta, {resumen.enumerar([_nombre_voz(n) for n in fuera])} {estado}"
        sub = f"En el Delta, {resumen.enumerar([_nombre_sub(n) for n in fuera])} {estado}"
        titular = "Atención en el Delta."
    elif residuo is not None and residuo >= UMBRAL_SUDESTADA:
        voz = f"En San Fernando, el río está {distancia_voz(residuo)} más alto que la marea de todos los días."
        sub = f"En San Fernando, el río está {distancia_sub(residuo)} más alto que la marea de todos los días."
        titular = f"En San Fernando, el río está {distancia_sub(residuo)} sobre la marea."
        nivel = "alerta"
    elif nivel == "normal" or residuo is not None:
        voz = sub = titular = "En Buenos Aires y el Delta, el río está tranquilo."
        nivel = "normal"
    else:
        voz = sub = titular = "No hay lecturas recientes del Delta."
        nivel = "sin"
    nivel_smn, evento = smn
    if nivel_smn not in ("verde", "sin"):
        extra = f" El Servicio Meteorológico tiene {SMN_TXT[nivel_smn]} por {evento} en el AMBA."
        voz += extra
        sub += extra
    return nivel, voz, sub, titular


def _elegir_ciudad(parana: dict | None, evac: list[str], alerta: list[str]) -> dict | None:
    puertos = _por_nombre(parana)
    if evac:
        return max((puertos[n] for n in evac), key=lambda p: p["altura"] - p["evacuacion"])
    if alerta:
        return min((puertos[n] for n in alerta), key=lambda p: p["evacuacion"] - p["altura"])
    normales = [p for p in puertos.values() if p["nivel"] == "normal"]
    return min(normales, key=lambda p: p["alerta"] - p["altura"]) if normales else None


def _ciudad(p: dict | None) -> tuple[str, str]:
    if p is None:
        return "Buscá tu ciudad en la web.", "Buscá tu ciudad en la web."
    nombre = _nombre_voz(p["puerto"])
    if p["nivel"] == "evacuacion":
        d = p["altura"] - p["evacuacion"]
        if round(d * 100) == 0:
            return (f"En {nombre}, el agua está justo en el nivel de evacuación.",) * 2
        resto = "por encima del nivel de evacuación."
        return (f"En {nombre}, el agua está {distancia_voz(d)} {resto}", f"En {nombre}, el agua está {distancia_sub(d)} {resto}")
    if p["nivel"] == "alerta":
        d = p["evacuacion"] - p["altura"]
        resto = "del nivel de evacuación."
    else:
        d = p["alerta"] - p["altura"]
        resto = "del nivel de alerta."
    return (f"En {nombre}, el agua está a {distancia_voz(d)} {resto}", f"En {nombre}, el agua está a {distancia_sub(d)} {resto}")


def _exceso_voz(d: float) -> str:
    return "justo en el nivel de evacuación" if round(d * 100) == 0 else distancia_voz(d)


def _exceso_sub(d: float) -> str:
    return "justo en el nivel" if round(d * 100) == 0 else distancia_sub(d)


def _peores(parana: dict | None, evac: list[str]) -> list[dict]:
    """Las ciudades en evacuación, de la que más pasó el nivel a la que menos."""
    puertos = _por_nombre(parana)
    return sorted((puertos[n] for n in evac), key=lambda p: p["evacuacion"] - p["altura"])


def _ciudades_criticas(peores: list[dict]) -> tuple[str, tuple[str, ...]]:
    """La peor con la frase completa y las que siguen con su número: (voz, subtítulos)."""
    primera_voz, primera_sub = _ciudad(peores[0])
    voces, subs = [primera_voz], [primera_sub]
    resto = peores[1:MAX_PEORES]
    for i, p in enumerate(resto):
        y = "Y en" if i == len(resto) - 1 else "En"
        d = p["altura"] - p["evacuacion"]
        voces.append(f"{y} {_nombre_voz(p['puerto'])}, {_exceso_voz(d)}.")
        subs.append(f"{y} {_nombre_sub(p['puerto'])}, {_exceso_sub(d)}.")
    return " ".join(voces), (_partir(primera_sub)[0],) + (_partir(" ".join(subs[1:])) if resto else ())


def _tendencia(peores: list[dict]) -> str:
    """Qué hace el río en la mayoría de las ciudades en evacuación; nada si no hay mayoría."""
    if len(peores) < 2:
        return ""
    for tendencia, frase in (("sube", "En la mayoría, el río sigue subiendo."),
                             ("baja", "En la mayoría, el río ya empieza a bajar."),
                             ("estable", "Por ahora, el río se mantiene estable.")):
        if sum(p.get("tendencia") == tendencia for p in peores) * 2 > len(peores):
            return frase
    return ""


def _resto_critico(peores: list[dict]) -> tuple[str, str]:
    """Las demás ciudades en evacuación y la tendencia: (voz, subtítulo)."""
    resto = peores[MAX_PEORES:]
    tendencia = _tendencia(peores)
    if resto:
        verbo = "también pasó" if len(resto) == 1 else "también pasaron"
        voz = f"{resumen.enumerar([_nombre_voz(p['puerto']) for p in resto])} {verbo} el nivel de evacuación."
        sub = f"{resumen.enumerar([_nombre_sub(p['puerto']) for p in resto])} {verbo} el nivel de evacuación."
    else:
        voz = sub = "Acá está todo el Paraná."
    return (f"{voz} {tendencia}".strip(), f"{sub} {tendencia}".strip())


def _costa_critica(costa_nivel: str, parana: dict | None, smn: tuple[str, str]) -> bool:
    """Con el Paraná en evacuación, la costa entra solo si el Delta está en alerta o hay alerta del SMN."""
    delta = any(p.get("rio") in resumen.RIOS_DELTA and p["nivel"] != "normal" for p in _por_nombre(parana).values())
    return delta or smn[0] not in ("verde", "sin")


def _avisos(parana: dict | None, costa_nivel: str, ahora: datetime) -> tuple[str, ...]:
    avisos = []
    hoy = ahora.astimezone(ART).date()
    fechas = {datetime.fromisoformat(p["ts"].replace("Z", "+00:00")).astimezone(ART).date()
              for p in _por_nombre(parana).values() if p.get("ts")}
    viejas = sorted(f for f in fechas if f < hoy)
    if viejas and max(fechas) < hoy:
        avisos.append(f"La lectura del Paraná es del {max(fechas):%d/%m}: todavía no llegó la de hoy.")
    if not parana or not parana.get("puertos"):
        avisos.append("No hay datos del Paraná.")
    if costa_nivel == "sin":
        avisos.append("No hay lecturas recientes del Delta ni de San Fernando.")
    return tuple(avisos)


# ---------- armado ----------

def armar(parana: dict | None, estado: dict | None, serie: dict | None, ahora: datetime) -> Guion:
    nivel, evac, alerta, _ = resumen._parana(parana)
    smn = _vigentes(estado, ahora)
    hoy_voz, hoy_sub = _hoy(evac, alerta, nivel)
    costa_nivel, costa_voz, costa_sub, costa_titular = _costa(parana, serie, smn, ahora)
    p = _elegir_ciudad(parana, evac, alerta)
    if evac:  # solo lo crítico: las ciudades en evacuación, de la peor a la menos grave
        peores = _peores(parana, evac)
        ciudad_voz, ciudad_subs = _ciudades_criticas(peores)
        rio_voz, rio_sub = _resto_critico(peores)
        pregunta = "¿Dónde está más complicado?"
        con_costa = _costa_critica(costa_nivel, parana, smn)
    else:
        ciudad_voz, ciudad_sub = _ciudad(p)
        ciudad_subs = (ciudad_sub[:-1],)
        rio_voz = "Acá está todo el Paraná, de lo más grave a lo más tranquilo."
        rio_sub = rio_voz
        pregunta = "¿Y en tu ciudad?"
        peores, con_costa = [], True
    bloques = (
        Bloque("hoy", hoy_voz, _partir(hoy_sub)),
        *((Bloque("costa", costa_voz, _partir(costa_sub)),) if con_costa else ()),
        Bloque("tuCiudad", pregunta, (pregunta,)),
        Bloque("ciudad", ciudad_voz, ciudad_subs),
        Bloque("rio", rio_voz, _partir(rio_sub)),
        Bloque("noOficial", "No somos un sistema oficial: ante una emergencia, Defensa Civil, ciento tres.",
               ("No somos un sistema oficial", "Ante una emergencia: Defensa Civil, 103")),
        Bloque("fin", "Seguí a Alerta Cuencas.", ()),
    )
    return Guion(
        fecha=ahora.astimezone(ART), ciudad=p["puerto"] if p else "", bloques=bloques,
        posteo=_posteo(evac, alerta, nivel, costa_sub if con_costa else "", peores),
        titular_portada=_titular(evac, alerta, nivel, costa_titular if con_costa else "", smn),
        nivel_parana=nivel, costa_nivel=costa_nivel if con_costa else "", avisos=_avisos(parana, costa_nivel, ahora),
        fichas=tuple(x["puerto"] for x in peores[:MAX_PEORES]) if peores else ((p["puerto"],) if p else ()),
    )


def _titular(evac: list[str], alerta: list[str], nivel: str, costa_titular: str, smn: tuple[str, str]) -> str:
    partes = []
    if evac:
        partes.append(f"El Paraná está en evacuación en {len(evac)} {'ciudad' if len(evac) == 1 else 'ciudades'}.")
    elif alerta:
        partes.append(f"El Paraná está en alerta en {len(alerta)} {'ciudad' if len(alerta) == 1 else 'ciudades'}.")
    elif nivel == "normal":
        partes.append("El Paraná está normal.")
    if costa_titular:
        partes.append(costa_titular)
    if smn[0] not in ("verde", "sin"):
        partes.append(f"Hay {SMN_TXT[smn[0]]} por {smn[1]} en el AMBA.")
    return " ".join(partes)


def _posteo(evac: list[str], alerta: list[str], nivel: str, costa_sub: str, peores: list[dict]) -> str:
    lineas = []
    if evac:
        n = len(evac)
        lineas.append(f"El Paraná tiene {n} {'ciudad' if n == 1 else 'ciudades'} en evacuación.")
        grave = [f"{_nombre_sub(p['puerto'])} (+{_exceso_sub(p['altura'] - p['evacuacion'])})" for p in peores[:MAX_PEORES]]
        lineas.append(f"Lo más grave: {resumen.enumerar(grave)}.")
    elif alerta:
        lineas.append(f"El Paraná está en alerta en {resumen.enumerar(alerta)}.")
    elif nivel == "normal":
        lineas.append("El Paraná está normal en todos los puertos.")
    if costa_sub:
        lineas.append(costa_sub)
    lineas.append(f"Buscá tu ciudad en {URL} (link en el perfil).")
    lineas.append("⚠️ No es un sistema oficial. Ante una emergencia: Defensa Civil 103.")
    lineas.append("Datos: Prefectura Naval, INA, Hidrografía Naval y SMN.")
    return "\n".join(lineas)
