"""Archivos del reel de cada día, en reels/AAAA-MM-DD/."""

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from alertas.publicar import imagenes
from alertas.reel.guion import Guion
from alertas.reel.tiempos import Subs


def _md(g: Guion, ahora: datetime) -> str:
    avisos = "\n".join(f"- ⚠️ {a}" for a in g.avisos) or "- Sin avisos."
    subs = "\n".join(f"| {b.clave} | {b.voz} | {' / '.join(b.subs) or 'Placa final'} |" for b in g.bloques)
    posteo = "\n".join(f"> {l}" for l in g.posteo.splitlines())
    return f"""# Reel {g.fecha:%d/%m/%Y}

**Estado:** preparado automáticamente el {ahora.astimezone(g.fecha.tzinfo):%d/%m a las %H:%M}; falta la locución.
**Ciudad de ejemplo:** {g.ciudad or "ninguna"}.

## Para revisar antes de grabar

{avisos}

## Texto para ElevenLabs

Julieta - Argentine Warm & Friendly · Eleven v4 · estabilidad 50 % · similitud 75 % ·
"Etiquetar automáticamente" apagado.

> {g.texto_voz}

## Guion por bloques

| Bloque | Voz | Subtítulos |
|---|---|---|
{subs}

## Texto del posteo

{posteo}

## Portada

> {g.titular_portada}

## Notas
"""


def preparar(carpeta: Path, g: Guion, ahora: datetime) -> list[Path]:
    """Guion, texto para la voz, texto del posteo y portada del día."""
    carpeta.mkdir(parents=True, exist_ok=True)
    rutas = {
        "guion.md": _md(g, ahora),
        "texto-voz.txt": g.texto_voz + "\n",
        "posteo.txt": g.posteo + "\n",
    }
    escritas = []
    for nombre, texto in rutas.items():
        ruta = carpeta / nombre
        ruta.write_text(texto, encoding="utf-8")
        escritas.append(ruta)
    escritas.append(guardar_guion(carpeta, g))
    portada = carpeta / "portada.png"
    imagenes.portada_reel(g.titular_portada, g.nivel_parana, g.costa_nivel, ahora).save(portada)
    escritas.append(portada)
    return escritas


def guardar_guion(carpeta: Path, g: Guion) -> Path:
    """El guion tal cual se preparó, para armar el video con el mismo texto que leyó la voz."""
    datos = asdict(g) | {"fecha": g.fecha.isoformat()}
    ruta = carpeta / "guion.json"
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return ruta


def reel_dia_js(carpeta: Path, g: Guion, t: dict[str, float], subs: Subs,
                fichas: list[tuple[float, str]] | None = None) -> Path:
    """La configuración del recorrido que lee scripts/reel/reel.js. FICHAS: [segundo, puerto] de
    cada ciudad que nombra la voz; la primera se escribe en el buscador y las demás se cambian solas."""
    datos = {"CIUDAD": g.ciudad, "T": t, "SUBS": [list(s) for s in subs],
             "FICHAS": [list(f) for f in (fichas or [])]}
    ruta = carpeta / "reel-dia.js"
    ruta.write_text(
        f"// Reel del {g.fecha:%d/%m/%Y}. Tiempos en segundos del audio (locucion.mp3). Generado por alertas.reel.\n"
        f"window.REEL = {json.dumps(datos, ensure_ascii=False, indent=2)};\n",
        encoding="utf-8",
    )
    return ruta
