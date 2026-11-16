"""Publicaciones para redes (Instagram) a partir del estado de cada poll.

En modo "prueba" (el único por ahora) arma la publicación y la deja en
web/publicaciones/ para revisarla, sin publicar nada en ningún lado.
"""

import json
import os
from datetime import datetime
from pathlib import Path

from alertas.publicar import imagenes, reglas, resumen

MODO = "prueba"
VERSION = 1
URL_WEB = "https://alertacuencas.github.io/"
ETIQUETAS = "#RíoParaná #Crecida #SantaFe #EntreRíos #Delta #RíoDeLaPlata #AMBA"
AVISO = "No es un sistema oficial. Ante una emergencia seguí a Defensa Civil de tu municipio (103)."


def epigrafe(r: resumen.Resumen, decision: reglas.Decision, ahora: datetime) -> str:
    """El texto de la publicación: lo nuevo primero, después el estado del día."""
    partes = []
    if decision.motivo == "cambio":
        partes.append(decision.detalle)
    partes.append(r.titular)
    if r.evacuacion:
        partes.append(f"🔴 En evacuación: {resumen.enumerar(r.evacuacion)}.")
    if r.alerta:
        partes.append(f"🟡 En alerta: {resumen.enumerar(r.alerta)}.")
    partes.append(f"🌊 Buenos Aires y el Delta: {r.costa_frase}")
    partes.append(f"⛈️ {r.lluvia_frase}")
    partes.append(f"Buscá tu ciudad en {URL_WEB}")
    partes.append(f"Datos de Prefectura Naval, INA, Hidrografía Naval y SMN · {imagenes.fecha_larga(ahora)}.")
    partes.append(AVISO)
    partes.append(ETIQUETAS)
    return "\n\n".join(partes)


def _leer(ruta: Path) -> dict:
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _escribir(ruta: Path, datos: dict) -> None:
    tmp = ruta.with_suffix(".tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, ruta)


def procesar(parana: dict | None, estado: dict | None, serie: dict | None,
             memoria_path: Path, salida: Path, ahora: datetime) -> reglas.Decision:
    """Decide, arma la publicación y la deja lista para revisar. Devuelve la decisión."""
    r = resumen.armar(parana, estado, serie)
    evac = r.evacuacion if parana else None          # sin datos del Paraná no hay "salieron todos"
    fuertes = r.zonas_fuertes if estado else None
    decision, memoria = reglas.decidir(evac, fuertes, _leer(memoria_path), ahora)

    salida.mkdir(parents=True, exist_ok=True)
    nombres = []
    for i, img in enumerate(imagenes.carrusel(r, ahora), start=1):
        nombre = f"{i}.png"
        img.save(salida / nombre, optimize=True)
        nombres.append(nombre)
    _escribir(salida / "publicacion.json", {
        "version": VERSION, "generado": ahora.isoformat(), "modo": MODO,
        "publicar": decision.publicar, "motivo": decision.motivo, "detalle": decision.detalle,
        "texto": epigrafe(r, decision, ahora), "imagenes": nombres, "historial": memoria["historial"],
    })
    memoria_path.parent.mkdir(parents=True, exist_ok=True)
    _escribir(memoria_path, memoria)
    return decision
