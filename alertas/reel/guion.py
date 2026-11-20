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
MAX_PEORES = 4          # ciudades en evacuación que el posteo nombra con su número
# Plan gratis de ElevenLabs: 10.000 créditos por mes (1 por letra). Con un reel por día, la voz tiene que
# rondar las 280 letras: nombra solo la ciudad más complicada; el resto queda en pantalla y en el posteo.
MAX_PEORES_VOZ = 1
MAX_VOZ = 340           # tope del peor caso (varios ríos, alerta SMN y otro río en alerta); lo controla un test
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
    mapa: tuple[str, ...] = ()    # puertos que el recorrido del mapa resalta (evacuación o, si no hay, alerta)
    otro_rio: str = ""            # el peor puerto en alerta de un río sin evacuación ("Además, el X…")

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
        mapa=tuple(d.get("mapa", ())), otro_rio=d.get("otro_rio", ""),
    )


# ---------- helpers ----------

def _nombre_voz(puerto: str) -> str:
    nombre = _nombre_sub(puerto)
    return "la ciudad de Paraná" if nombre == "Paraná" else nombre


def _nombre_sub(puerto: str) -> str:
    return re.sub(r"\s*\(.*?\)", "", puerto).strip()


def _sobre(p: dict) -> str:
    """', sobre el Uruguay' para los puertos que no son del Paraná (hay dos San Javier)."""
    c = resumen.cuenca(p)
    return "" if c == resumen.CUENCA_DEFECTO else f", sobre el {c}"


def _lugar_voz(p: dict) -> str:
    return _nombre_voz(p["puerto"]) + _sobre(p)


def _lugar_sub(p: dict) -> str:
    return _nombre_sub(p["puerto"]) + _sobre(p)


def _solo_parana(parana: dict | None) -> bool:
    return {resumen.cuenca(p) for p in _por_nombre(parana).values()} <= {resumen.CUENCA_DEFECTO}


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

def _hoy(parana: dict | None, nivel: str) -> tuple[str, str]:
    """Devuelve (voz, subtítulo con cifras): cuántas ciudades y de qué ríos, lo más grave primero."""
    puertos = list(_por_nombre(parana).values())
    for estado, txt in (("evacuacion", "evacuación"), ("alerta", "alerta")):
        lista = [p for p in puertos if p["nivel"] == estado]
        if lista:
            return _hoy_nivel(lista, estado, txt)
    if nivel == "normal":
        voz = "Hoy, el Paraná está normal en todos los puertos." if _solo_parana(parana) \
            else "Hoy, los ríos están normales en todos los puertos."
    else:
        voz = "Hoy, no hay lecturas recientes de los ríos."
    return voz, voz


def _hoy_nivel(lista: list[dict], estado: str, txt: str) -> tuple[str, str]:
    grupos = resumen.por_cuenca(lista)
    n = len(lista)
    if len(grupos) > 1:
        voz = [f"{en_letras(len(ps), femenino=True)} sobre el {c}" for c, ps in grupos]
        sub = [f"{len(ps)} sobre el {c}" for c, ps in grupos]
        return (f"Hoy, {en_letras(n, femenino=True)} ciudades están en {txt}: {resumen.enumerar(voz)}.",
                f"Hoy, {n} ciudades están en {txt}: {resumen.enumerar(sub)}.")
    c = grupos[0][0]
    if estado == "evacuacion":
        if n == 1:
            return (f"Hoy, una ciudad del {c} está en evacuación: {_nombre_voz(lista[0]['puerto'])}.",
                    f"Hoy, una ciudad del {c} está en evacuación: {_nombre_sub(lista[0]['puerto'])}.")
        return (f"Hoy, {en_letras(n, femenino=True)} ciudades del {c} están en evacuación.",
                f"Hoy, {n} ciudades del {c} están en evacuación.")
    if n == 1:
        return (f"Hoy, el {c} está en alerta en {_nombre_voz(lista[0]['puerto'])}.",
                f"Hoy, el {c} está en alerta en {_nombre_sub(lista[0]['puerto'])}.")
    a, b = lista[0]["puerto"], lista[-1]["puerto"]  # en el orden del río
    return (f"Hoy, {en_letras(n, femenino=True)} ciudades del {c} están en alerta. Desde {_nombre_voz(a)} hasta {_nombre_voz(b)}.",
            f"Hoy, {n} ciudades del {c} están en alerta. Desde {_nombre_sub(a)} hasta {_nombre_sub(b)}.")


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
        extra = f" Hay {SMN_TXT[nivel_smn]} por {evento} en el AMBA."
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
    nombre, nombre_sub = _lugar_voz(p), _lugar_sub(p)
    if p["nivel"] == "evacuacion":
        d = p["altura"] - p["evacuacion"]
        if round(d * 100) == 0:
            return (f"En {nombre}, el agua está justo en el nivel de evacuación.",
                    f"En {nombre_sub}, el agua está justo en el nivel de evacuación.")
        resto = "arriba del nivel de evacuación."
        return (f"En {nombre}, está {distancia_voz(d)} {resto}", f"En {nombre_sub}, está {distancia_sub(d)} {resto}")
    if p["nivel"] == "alerta":
        d = p["evacuacion"] - p["altura"]
        resto = "del nivel de evacuación."
    else:
        d = p["alerta"] - p["altura"]
        resto = "del nivel de alerta."
    return (f"En {nombre}, el agua está a {distancia_voz(d)} {resto}", f"En {nombre_sub}, el agua está a {distancia_sub(d)} {resto}")


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
    resto = peores[1:MAX_PEORES_VOZ]
    for i, p in enumerate(resto):
        y = "Y en" if i == len(resto) - 1 else "En"
        d = p["altura"] - p["evacuacion"]
        voces.append(f"{y} {_lugar_voz(p)}, {_exceso_voz(d)}.")
        subs.append(f"{y} {_lugar_sub(p)}, {_exceso_sub(d)}.")
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


def _alerta_otros_rios(parana: dict | None, peores: list[dict]) -> list[dict]:
    """Puertos en alerta de los ríos que no tienen ciudades en evacuación, del más grave al menos."""
    con_evac = {resumen.cuenca(p) for p in peores}
    return sorted((p for p in _por_nombre(parana).values()
                   if p["nivel"] == "alerta" and resumen.cuenca(p) not in con_evac), key=resumen._gravedad)


def _ademas_alerta(parana: dict | None, peores: list[dict]) -> str:
    """Los ríos que no tienen ciudades en evacuación pero sí en alerta, sin nombrar ciudades."""
    alerta = _alerta_otros_rios(parana, peores)
    rios = [f"el {c}" for c, _ in resumen.por_cuenca(alerta)]
    if not rios:
        return ""
    return f"Además, {resumen.enumerar(rios)} {'está' if len(rios) == 1 else 'están'} en alerta."


def _resto_critico(peores: list[dict], parana: dict | None = None) -> tuple[str, str]:
    """Los ríos en alerta sin evacuación o, si no hay, la invitación a ver el resto: (voz, subtítulo).
    Las demás ciudades y la tendencia van en pantalla y en el posteo, no en la voz (créditos)."""
    ademas = _ademas_alerta(parana, peores)
    voz = ademas or ("Acá, todo el Paraná." if _solo_parana(parana) else "Acá, todos los ríos.")
    return voz, voz


def _delta_critico(parana: dict | None) -> bool:
    return any(p.get("rio") in resumen.RIOS_DELTA and p["nivel"] != "normal" for p in _por_nombre(parana).values())


def _costa_critica(costa: tuple[str, str, str, str], parana: dict | None,
                   smn: tuple[str, str]) -> tuple[str, str, str, str] | None:
    """Con el Paraná en evacuación entra solo lo crítico de la costa: el Delta en alerta (con la del SMN, si
    hay) o, si no, solo la alerta del SMN; nunca 'el río está tranquilo' ni la sudestada de San Fernando."""
    if _delta_critico(parana):
        return costa
    if smn[0] not in ("verde", "sin"):
        frase = f"Hay {SMN_TXT[smn[0]]} por {smn[1]} en el AMBA."
        return "", frase, frase, ""
    return None


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
    hoy_voz, hoy_sub = _hoy(parana, nivel)
    costa = _costa(parana, serie, smn, ahora)
    costa_nivel = costa[0]
    p = _elegir_ciudad(parana, evac, alerta)
    if evac:  # solo lo crítico: las ciudades en evacuación, de la peor a la menos grave
        peores = _peores(parana, evac)
        ciudad_voz, ciudad_subs = _ciudades_criticas(peores)
        rio_voz, rio_sub = _resto_critico(peores, parana)
        pregunta = "¿Dónde está peor?"
        critica = _costa_critica(costa, parana, smn)
        con_costa = critica is not None
        costa = critica or costa
    else:
        ciudad_voz, ciudad_sub = _ciudad(p)
        ciudad_subs = (ciudad_sub[:-1],)
        rio_voz = "Acá, todo el Paraná." if _solo_parana(parana) else "Acá, todos los ríos."
        rio_sub = rio_voz
        pregunta = "¿Y en tu ciudad?"
        peores, con_costa = [], True
    costa_nivel_portada, costa_voz, costa_sub, costa_titular = costa
    bloques = (
        Bloque("hoy", hoy_voz, _partir(hoy_sub)),
        *((Bloque("costa", costa_voz, _partir(costa_sub)),) if con_costa else ()),
        Bloque("tuCiudad", pregunta, (pregunta,)),
        Bloque("ciudad", ciudad_voz, ciudad_subs),
        Bloque("rio", rio_voz, _partir(rio_sub)),
        Bloque("noOficial", "No es oficial. Emergencias, ciento tres.",
               ("No es un sistema oficial", "Emergencias: Defensa Civil, 103")),
        Bloque("fin", "Seguí a Alerta Cuencas.", ()),
    )
    return Guion(
        fecha=ahora.astimezone(ART), ciudad=p["puerto"] if p else "", bloques=bloques,
        posteo=_posteo(parana, alerta, costa_sub if con_costa else "", peores),
        titular_portada=_titular(parana, costa_titular if con_costa else "", smn),
        nivel_parana=nivel, costa_nivel=costa_nivel_portada if con_costa else "", avisos=_avisos(parana, costa_nivel, ahora),
        fichas=tuple(x["puerto"] for x in peores[:MAX_PEORES_VOZ]) if peores else ((p["puerto"],) if p else ()),
        mapa=_mapa(parana, evac, alerta),
        otro_rio=next((x["puerto"] for x in _alerta_otros_rios(parana, peores)), "") if peores else "",
    )


def _mapa(parana: dict | None, evac: list[str], alerta: list[str]) -> tuple[str, ...]:
    nombres = set(evac or alerta)
    return tuple(p["puerto"] for p in sorted(_por_nombre(parana).values(), key=resumen._gravedad) if p["puerto"] in nombres)


def _titular(parana: dict | None, costa_titular: str, smn: tuple[str, str]) -> str:
    partes = [t] if (t := resumen.titular_rios(parana)) else []
    if costa_titular:
        partes.append(costa_titular)
    if smn[0] not in ("verde", "sin"):
        partes.append(f"Hay {SMN_TXT[smn[0]]} por {smn[1]} en el AMBA.")
    return " ".join(partes)


def _posteo(parana: dict | None, alerta: list[str], costa_sub: str, peores: list[dict]) -> str:
    lineas = [t] if (t := resumen.titular_rios(parana)) else []
    if peores:
        grave = [f"{_lugar_sub(p)} (+{_exceso_sub(p['altura'] - p['evacuacion'])})" for p in peores[:MAX_PEORES]]
        lineas.append(f"Lo más grave: {resumen.enumerar(grave)}.")
        if tendencia := _tendencia(peores):
            lineas.append(tendencia)
    elif alerta:
        lineas.append(f"En alerta: {resumen.enumerar(alerta)}.")
    if costa_sub:
        lineas.append(costa_sub)
    lineas.append(f"Buscá tu ciudad en {URL} (link en el perfil).")
    lineas.append("⚠️ No es un sistema oficial. Ante una emergencia: Defensa Civil 103.")
    lineas.append("Datos: Prefectura Naval, INA, Hidrografía Naval y SMN.")
    return "\n".join(lineas)
