"""Resumen en lenguaje claro del estado de hoy, para publicar en redes.

Es el mismo criterio que la portada de la web (web/app.js): titular, Paraná, costa y
tormentas. Función pura: recibe los JSON que arma el poll y devuelve texto.
"""

from dataclasses import dataclass, field

GRAVEDAD = {"evacuacion": 0, "alerta": 1, "normal": 2}
SMN_GRAVEDAD = {"rojo": 0, "naranja": 1, "amarillo": 2, "verde": 3}
SMN_TXT = {"rojo": "alerta roja", "naranja": "alerta naranja", "amarillo": "alerta amarilla", "verde": "sin alertas"}
NIVEL_TXT = {"evacuacion": "evacuación", "alerta": "alerta", "normal": "normal"}
RIOS_DELTA = {"PARANADELASPALMAS", "PARANAGUAZU", "PARANAIBICUY", "DELTA PARANA", "IBICUY",
              "BARADERO", "CANALGAFOTRE", "CHANA", "LUJAN"}  # los últimos, códigos del INA
MAX_AFECTADOS = 6
CUENCA_DEFECTO = "Paraná"  # datos viejos sin cuenca: eran todos del Paraná


@dataclass(frozen=True)
class Resumen:
    titular: str
    nivel_parana: str                 # evacuacion | alerta | normal | sin
    evacuacion: list[str]             # en el orden del río (norte a sur)
    alerta: list[str]
    afectados: list[dict]             # puertos más graves primero, hasta MAX_AFECTADOS
    costa_nivel: str
    costa_frase: str
    lluvia_nivel: str                 # nivel SMN más grave en el AMBA
    lluvia_frase: str
    zonas_fuertes: list[str] = field(default_factory=list)  # ids con alerta naranja o roja


def enumerar(nombres: list[str]) -> str:
    if len(nombres) <= 1:
        return nombres[0] if nombres else ""
    return f"{', '.join(nombres[:-1])} y {nombres[-1]}"


def metros(v: float) -> str:
    return f"{v:.2f}".replace(".", ",") + " m"


def distancia(v: float) -> str:
    cm = round(abs(v) * 100)
    return metros(abs(v)) if cm >= 100 else f"{cm} cm"


def frase_puerto(p: dict) -> str:
    if p["nivel"] == "evacuacion":
        return f"pasa por {distancia(p['altura'] - p['evacuacion'])} el nivel de evacuación"
    if p["nivel"] == "alerta":
        return f"a {distancia(p['evacuacion'] - p['altura'])} del nivel de evacuación"
    return f"a {distancia(p['alerta'] - p['altura'])} del nivel de alerta"


def _gravedad(p: dict) -> tuple:
    return (p.get("viejo", False), GRAVEDAD.get(p["nivel"], 3), -p["altura"] / p["evacuacion"])


def cuenca(p: dict) -> str:
    return p.get("cuenca") or CUENCA_DEFECTO


def por_cuenca(puertos: list[dict]) -> list[tuple[str, list[dict]]]:
    """Agrupa por río: primero el río del puerto más grave; adentro, del más grave al menos."""
    grupos: dict[str, list[dict]] = {}
    for p in sorted(puertos, key=_gravedad):
        grupos.setdefault(cuenca(p), []).append(p)
    return list(grupos.items())


def _ciudades(n: int) -> str:
    return f"{n} {'ciudad' if n == 1 else 'ciudades'}"


def frase_nivel(puertos: list[dict], nivel: str) -> str:
    """'El Paraná está en evacuación en 8 ciudades y el Uruguay en 1.' (de lo más grave a lo menos)."""
    grupos = por_cuenca(puertos)
    (c0, ps0), resto = grupos[0], grupos[1:]
    otros = [f"el {c} en {len(ps)}" for c, ps in resto]
    cola = f", {', '.join(otros[:-1])} y {otros[-1]}" if len(otros) > 1 else f" y {otros[0]}" if otros else ""
    return f"El {c0} está en {NIVEL_TXT[nivel]} en {_ciudades(len(ps0))}{cola}."


def titular_rios(parana: dict | None) -> str:
    """Lo más grave primero: las ciudades en evacuación y, después, los ríos que solo tienen alerta."""
    puertos = [p for p in (parana or {}).get("puertos", []) if not p.get("viejo")]
    evac = [p for p in puertos if p["nivel"] == "evacuacion"]
    alerta = [p for p in puertos if p["nivel"] == "alerta"]
    if evac:
        con_evac = {cuenca(p) for p in evac}
        solo_alerta = [p for p in alerta if cuenca(p) not in con_evac]
        return " ".join([frase_nivel(evac, "evacuacion")] + ([frase_nivel(solo_alerta, "alerta")] if solo_alerta else []))
    if alerta:
        return frase_nivel(alerta, "alerta")
    if puertos:
        return "El Paraná está normal." if {cuenca(p) for p in puertos} == {CUENCA_DEFECTO} else "Los ríos están normales."
    return ""


def _parana(parana: dict | None) -> tuple[str, list[str], list[str], list[dict]]:
    puertos = [p for p in (parana or {}).get("puertos", []) if not p.get("viejo")]
    evac = [p["puerto"] for p in puertos if p["nivel"] == "evacuacion"]
    alerta = [p["puerto"] for p in puertos if p["nivel"] == "alerta"]
    nivel = "evacuacion" if evac else "alerta" if alerta else "normal" if puertos else "sin"
    afectados = sorted(puertos, key=_gravedad)[:MAX_AFECTADOS]
    return nivel, evac, alerta, afectados


def _costa(parana: dict | None, serie: dict | None) -> tuple[str, str]:
    delta = sorted((p for p in (parana or {}).get("puertos", [])
                    if p.get("rio") in RIOS_DELTA and not p.get("viejo")), key=_gravedad)
    residuos = ((serie or {}).get("estaciones", {}).get("SFER", {}) or {}).get("residuo") or []
    partes = []
    if residuos:
        r = residuos[-1][1]
        partes.append(f"El agua está {distancia(r)} {'más alta' if r >= 0 else 'más baja'} que la marea de todos los días.")
    nivel = delta[0]["nivel"] if delta else "sin"
    if delta:
        fuera = [p["puerto"] for p in delta if p["nivel"] != "normal"]
        partes.append(f"En el Delta: {enumerar(fuera)} en {NIVEL_TXT[nivel]}." if fuera
                      else "Ninguna escala del Delta está en alerta.")
    return nivel, " ".join(partes) or "Sin datos recientes del río."


def _lluvia(estado: dict | None) -> tuple[str, str, list[str], str]:
    zonas = (estado or {}).get("zonas", {})
    con = sorted(((i, z) for i, z in zonas.items() if z.get("alertas")), key=lambda iz: SMN_GRAVEDAD.get(iz[1]["nivel_smn"], 9))
    fuertes = [i for i, z in con if z["nivel_smn"] in ("naranja", "rojo")]
    if not con:
        return ("verde" if zonas else "sin"), "El Servicio Meteorológico no tiene alertas para las cuencas del AMBA.", [], ""
    nivel = con[0][1]["nivel_smn"]
    evento = con[0][1]["alertas"][0]["evento"].lower()
    nombres = [z["nombre"] for _, z in con]
    return nivel, f"{SMN_TXT[nivel].capitalize()} por {evento} en {enumerar(nombres)}.", fuertes, evento


def _titular(rios: str, hay_evac: bool, costa: str, lluvia: str, evento: str) -> str:
    partes = [rios] if rios else []
    if costa not in ("normal", "sin"):
        partes.append("Atención en el Delta.")
    elif not hay_evac:  # lo más grave primero: con ciudades en evacuación, la costa tranquila no es noticia
        partes.append("En Buenos Aires y el Delta, el río está tranquilo.")
    if lluvia not in ("verde", "sin"):
        partes.append(f"Hay {SMN_TXT[lluvia]} por {evento} en el AMBA.")
    return " ".join(partes)


def armar(parana: dict | None, estado: dict | None, serie: dict | None) -> Resumen:
    nivel, evac, alerta, afectados = _parana(parana)
    costa_nivel, costa_frase = _costa(parana, serie)
    lluvia_nivel, lluvia_frase, fuertes, evento = _lluvia(estado)
    return Resumen(
        titular=_titular(titular_rios(parana), bool(evac), costa_nivel, lluvia_nivel, evento), nivel_parana=nivel,
        evacuacion=evac, alerta=alerta, afectados=afectados, costa_nivel=costa_nivel, costa_frase=costa_frase,
        lluvia_nivel=lluvia_nivel, lluvia_frase=lluvia_frase, zonas_fuertes=fuertes,
    )
