"""Cuándo publicar en redes.

- Un resumen por día, en la primera corrida desde las 8 (hora argentina).
- Una publicación extra si cambia algo importante: un puerto entra o sale del nivel de
  evacuación, o el SMN emite una alerta naranja o roja nueva para una cuenca del AMBA.
- Nunca más de MAX_POR_DIA publicaciones por día.

La memoria (qué se vio y qué se publicó) se guarda entre corridas en un JSON.
Si una fuente no respondió, no se toma como "todo volvió a la normalidad": se
conserva lo último que se vio de esa fuente.
"""

from dataclasses import dataclass
from datetime import datetime

from alertas.tiempo import ART

HORA_DIARIO = 8
MAX_POR_DIA = 4
MAX_HISTORIAL = 30


@dataclass(frozen=True)
class Decision:
    publicar: bool
    motivo: str        # "diario" | "cambio" | "tope" | "sin_novedad"
    detalle: str       # frase para el epígrafe o para la página de revisión


def _dia(ahora: datetime) -> str:
    return ahora.astimezone(ART).date().isoformat()


def decidir(evacuacion: list[str] | None, zonas_fuertes: list[str] | None,
            memoria: dict, ahora: datetime) -> tuple[Decision, dict]:
    """Devuelve la decisión y la memoria nueva (no modifica la recibida).

    `evacuacion` o `zonas_fuertes` en None significa "la fuente no respondió".
    """
    vista = memoria.get("vista")
    previa_evac = set(vista["evacuacion"]) if vista else None
    previa_smn = set(vista["zonas_fuertes"]) if vista else None
    evac = set(evacuacion) if evacuacion is not None else (previa_evac or set())
    smn = set(zonas_fuertes) if zonas_fuertes is not None else (previa_smn or set())

    cambios = []
    if vista is not None:
        if entraron := sorted(evac - previa_evac):
            cambios.append(f"{_lista(entraron)} {'entró' if len(entraron) == 1 else 'entraron'} en nivel de evacuación.")
        if salieron := sorted(previa_evac - evac):
            cambios.append(f"{_lista(salieron)} {'salió' if len(salieron) == 1 else 'salieron'} del nivel de evacuación.")
        if sorted(smn - previa_smn):
            cambios.append("El Servicio Meteorológico emitió una alerta naranja o roja para el AMBA.")

    hoy = _dia(ahora)
    publicadas_hoy = [ts for ts in memoria.get("publicadas", []) if ts.startswith(hoy)]
    toca_diario = memoria.get("ultimo_diario") != hoy and ahora.astimezone(ART).hour >= HORA_DIARIO

    if cambios:
        decision = Decision(True, "cambio", " ".join(cambios))
    elif toca_diario:
        decision = Decision(True, "diario", "Resumen del día.")
    else:
        decision = Decision(False, "sin_novedad", "Nada nuevo desde la última corrida.")
    if decision.publicar and len(publicadas_hoy) >= MAX_POR_DIA:
        decision = Decision(False, "tope", f"Ya hubo {MAX_POR_DIA} publicaciones hoy. {decision.detalle}")

    nueva = {
        "vista": {"evacuacion": sorted(evac), "zonas_fuertes": sorted(smn)},
        "publicadas": [*publicadas_hoy, *([_dia_hora(ahora)] if decision.publicar else [])],
        # Una publicación desde las 8 cuenta como el resumen del día; una de madrugada, no.
        "ultimo_diario": hoy if decision.publicar and ahora.astimezone(ART).hour >= HORA_DIARIO
        else memoria.get("ultimo_diario"),
        "historial": [
            {"ts": ahora.isoformat(), "publicar": decision.publicar, "motivo": decision.motivo, "detalle": decision.detalle},
            *memoria.get("historial", []),
        ][:MAX_HISTORIAL],
    }
    return decision, nueva


def _dia_hora(ahora: datetime) -> str:
    return ahora.astimezone(ART).isoformat(timespec="minutes")


def _lista(nombres: list[str]) -> str:
    return nombres[0] if len(nombres) == 1 else f"{', '.join(nombres[:-1])} y {nombres[-1]}"
