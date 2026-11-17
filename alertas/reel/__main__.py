"""Comandos del reel diario.

    python -m alertas.reel preparar --datos web/data --reels reels
        Arma reels/AAAA-MM-DD/ con el guion, el texto para ElevenLabs, el posteo y la portada.

    python -m alertas.reel tiempos --datos web/data --dia reels/AAAA-MM-DD
        Transcribe reels/AAAA-MM-DD/locucion.mp3 y escribe reel-dia.js con los tiempos.
        Necesita faster-whisper e imageio-ffmpeg (uv run --with ...).
"""

import argparse
import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from alertas.reel import guion, salida, tiempos
from alertas.tiempo import ART, ahora_utc

log = logging.getLogger("alertas.reel")


def _leer(datos: Path, nombre: str) -> dict | None:
    ruta = datos / nombre
    if not ruta.exists():
        log.warning("falta %s", ruta)
        return None
    return json.loads(ruta.read_text(encoding="utf-8"))


def _guion(datos: Path, ahora: datetime) -> guion.Guion:
    return guion.armar(_leer(datos, "parana.json"), _leer(datos, "estado.json"), _leer(datos, "serie.json"), ahora)


def transcribir(audio: Path) -> tuple[tiempos.Palabras, float]:
    """Palabras con su segundo de inicio y la duración total (faster-whisper, CPU)."""
    import imageio_ffmpeg
    import numpy as np
    from faster_whisper import WhisperModel

    pcm = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-loglevel", "error", "-i", str(audio),
                          "-f", "f32le", "-ac", "1", "-ar", "16000", "-"], capture_output=True, check=True).stdout
    muestras = np.frombuffer(pcm, np.float32)
    modelo = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=2)
    segmentos, _ = modelo.transcribe(muestras, language="es", word_timestamps=True)
    palabras = [(w.word.strip(), round(w.start, 2)) for s in segmentos for w in s.words]
    return palabras, round(len(muestras) / 16000, 2)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="alertas.reel")
    parser.add_argument("comando", choices=["preparar", "tiempos"])
    parser.add_argument("--datos", type=Path, default=Path("web/data"))
    parser.add_argument("--reels", type=Path, default=Path("reels"))
    parser.add_argument("--dia", type=Path, help="carpeta del día (por defecto, la de hoy)")
    parser.add_argument("--ahora", type=datetime.fromisoformat,
                        help="momento en que se preparó el guion (ISO), para que el armado use el mismo texto")
    args = parser.parse_args(argv)

    ahora = args.ahora or ahora_utc()
    dia = args.dia or args.reels / f"{ahora.astimezone(ART):%Y-%m-%d}"
    if args.comando == "preparar":
        g = _guion(args.datos, ahora)
        for ruta in salida.preparar(dia, g, ahora):
            log.info("escrito %s", ruta)
        (dia / "ahora.txt").write_text(ahora.isoformat() + "\n", encoding="utf-8")
        for aviso in g.avisos:
            log.warning("revisar: %s", aviso)
        print(dia)
        return 0

    # el armado usa el guion guardado al preparar: así coincide con lo que leyó la voz
    guardado = dia / "guion.json"
    g = guion.cargar(guardado) if guardado.exists() else _guion(args.datos, ahora)
    audio = dia / "locucion.mp3"
    if not audio.exists():
        log.error("falta %s", audio)
        return 1
    palabras, duracion = transcribir(audio)
    log.info("transcripción: %s", " ".join(w for w, _ in palabras))
    t, subs = tiempos.calcular(g, palabras, duracion)
    log.info("escrito %s (duración %.1f s)", salida.reel_dia_js(dia, g, t, subs), duracion)
    return 0


if __name__ == "__main__":
    sys.exit(main())
