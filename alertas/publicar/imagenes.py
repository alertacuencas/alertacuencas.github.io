"""Carrusel de 3 imágenes (1080×1350, el formato vertical de Instagram) en el estilo de la web.

1. Portada: fecha y titular.
2. Dónde está más alto el Paraná: las varas de escala de los puertos más afectados.
3. Buenos Aires, el Delta y las tormentas.
"""

from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from alertas.publicar.resumen import NIVEL_TXT, SMN_TXT, Resumen, frase_puerto, metros
from alertas.tiempo import ART

ANCHO, ALTO = 1080, 1350
MARGEN = 80
TIPOS = Path(__file__).resolve().parent.parent / "tipografias"
MAIZ, MAIZ_HONDO, SUPERFICIE = "#f4ebdd", "#e9dcc6", "#fbf6ee"
CARBON, CARBON_SUAVE, LINEA = "#1e1a16", "#5a5047", "#d8c9b0"
CARTEL, CARTEL_TEXTO, AGUA = "#4a2f18", "#fbf6ee", "#5b9ec4"
COLOR = {"evacuacion": "#b3261e", "alerta": "#e0a526", "normal": "#3f6b3a", "sin": "#9a8f82",
         "rojo": "#b3261e", "naranja": "#d9661b", "amarillo": "#e0a526", "verde": "#3f6b3a"}
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
URL = "alertacuencas.github.io"
CUENTA = "@alertacuencas"


def _archivo(tam: int, peso: int = 800, ancho: int = 85) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(TIPOS / "Archivo-variable.ttf"), tam)
    f.set_variation_by_axes([peso, ancho])  # ejes: Weight, Width
    return f


def _mono(tam: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(TIPOS / "IBMPlexMono-SemiBold.ttf"), tam)


def _lineas(texto: str, fuente: ImageFont.FreeTypeFont, ancho: int) -> list[str]:
    lineas, actual = [], ""
    for palabra in texto.split():
        prueba = f"{actual} {palabra}".strip()
        if fuente.getlength(prueba) <= ancho or not actual:
            actual = prueba
        else:
            lineas.append(actual)
            actual = palabra
    return [*lineas, actual] if actual else lineas


def _parrafo(d: ImageDraw.ImageDraw, xy: tuple[int, int], texto: str, fuente, ancho: int,
             color: str = CARBON, interlinea: float = 1.18) -> int:
    """Dibuja un párrafo y devuelve la coordenada y donde termina."""
    x, y = xy
    alto = round(fuente.size * interlinea)
    for linea in _lineas(texto, fuente, ancho):
        d.text((x, y), linea, font=fuente, fill=color)
        y += alto
    return y


def fecha_larga(ahora: datetime) -> str:
    a = ahora.astimezone(ART)
    return f"{DIAS[a.weekday()]} {a.day} de {MESES[a.month - 1]}"


def _marco(numero: int, total: int, ahora: datetime) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (ANCHO, ALTO), MAIZ)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, ANCHO, 110], fill=CARTEL)
    # la "vara" de la marca: franjas y agua
    for i in range(7):
        d.rectangle([MARGEN, 30 + i * 8, MARGEN + 14, 33 + i * 8], fill=CARTEL_TEXTO)
    d.rectangle([MARGEN, 66, MARGEN + 14, 82], fill=AGUA)
    d.text((MARGEN + 34, 32), "ALERTA CUENCAS", font=_archivo(40, 800, 80), fill=CARTEL_TEXTO)
    d.text((ANCHO - MARGEN, 42), f"{CUENTA}  {numero}/{total}", font=_mono(26), fill=CARTEL_TEXTO, anchor="ra")
    d.line([MARGEN, ALTO - 140, ANCHO - MARGEN, ALTO - 140], fill=LINEA, width=2)
    d.text((MARGEN, ALTO - 118), "No es un sistema oficial. Emergencias: Defensa Civil (103).",
           font=_archivo(28, 600, 100), fill=CARBON_SUAVE)
    d.text((MARGEN, ALTO - 70), f"{fecha_larga(ahora)} · {URL}", font=_mono(24), fill=CARBON_SUAVE)
    return img, d


def _etiqueta(d: ImageDraw.ImageDraw, xy: tuple[int, int], texto: str) -> int:
    f = _mono(26)
    x, y = xy
    ancho = round(f.getlength(texto.upper()))
    d.rounded_rectangle([x, y, x + ancho + 28, y + 46], radius=5, fill=CARTEL)
    d.text((x + 14, y + 9), texto.upper(), font=f, fill=CARTEL_TEXTO)
    return y + 46


def portada(r: Resumen, ahora: datetime) -> Image.Image:
    img, d = _marco(1, 3, ahora)
    y = _etiqueta(d, (MARGEN, 180), f"Hoy · {fecha_larga(ahora)}") + 50
    d.rectangle([0, y, 22, y + 620], fill=COLOR[r.nivel_parana])
    tam = 92 if len(r.titular) < 150 else 80
    _parrafo(d, (MARGEN, y), r.titular, _archivo(tam, 800, 82), ANCHO - 2 * MARGEN, interlinea=1.05)
    _estados(d, ALTO - 330, (
        ("Río Paraná", r.nivel_parana, NIVEL_TXT.get(r.nivel_parana, "sin datos")),
        ("Buenos Aires y el Delta", r.costa_nivel, NIVEL_TXT.get(r.costa_nivel, "sin datos")),
        ("Tormentas · AMBA", r.lluvia_nivel, SMN_TXT.get(r.lluvia_nivel, "sin datos")),
    ))
    return img


def _estados(d: ImageDraw.ImageDraw, y: int, filas: tuple) -> None:
    """Tres franjas cortas con el color y el estado de cada zona."""
    f_zona, f_estado = _archivo(30, 600, 95), _archivo(30, 800, 85)
    for i, (zona, nivel, estado) in enumerate(filas):
        yy = y + i * 54
        color = COLOR.get(nivel, COLOR["sin"])
        d.ellipse([MARGEN, yy + 6, MARGEN + 26, yy + 32], fill=color)
        d.text((MARGEN + 44, yy), zona, font=f_zona, fill=CARBON)
        d.text((ANCHO - MARGEN, yy), estado.upper(), font=f_estado, fill=color, anchor="ra")


def _vara(d: ImageDraw.ImageDraw, x: int, y: int, ancho: int, alto: int, p: dict) -> None:
    """La escala hidrométrica: franjas, agua hasta la altura de hoy y marcas de alerta y evacuación."""
    tope = max(p["evacuacion"] * 1.35, p["altura"] * 1.1)
    nivel_y = lambda v: y + alto - round(min(1, max(0, v / tope)) * alto)  # noqa: E731
    d.rectangle([x, y, x + ancho, y + alto], fill=SUPERFICIE, outline=CARBON, width=3)
    evac = p["nivel"] == "evacuacion"
    agua = COLOR["evacuacion"] if evac else AGUA
    superficie = nivel_y(p["altura"])
    d.rectangle([x + 3, superficie, x + ancho - 3, y + alto - 3], fill=agua)
    for yy in range(y + 6, y + alto - 4, 16):  # las franjas de la escala se ven también bajo el agua
        d.rectangle([x + 3, yy, x + ancho // 2, yy + 7], fill=CARBON if yy < superficie else ("#e8c9c0" if evac else "#d3e6f1"))
    for v, color in ((p["alerta"], COLOR["alerta"]), (p["evacuacion"], COLOR["evacuacion"])):
        yy = nivel_y(v)
        d.rectangle([x - 10, yy - 4, x + ancho + 10, yy + 4], fill=color)


def puertos(r: Resumen, ahora: datetime) -> Image.Image:
    img, d = _marco(2, 3, ahora)
    y = _etiqueta(d, (MARGEN, 160), "Río Paraná") + 26
    y = _parrafo(d, (MARGEN, y), "Dónde está más alto el río", _archivo(64, 800, 85), ANCHO - 2 * MARGEN) + 24
    if not r.afectados:
        _parrafo(d, (MARGEN, y), "No hay alturas recientes del Paraná.", _archivo(40, 500, 100), ANCHO - 2 * MARGEN)
        return img
    fila = (ALTO - 190 - y) // len(r.afectados)
    alto_vara = min(130, fila - 26)
    for i, p in enumerate(r.afectados):
        top = y + i * fila
        _vara(d, MARGEN + 10, top + (fila - alto_vara) // 2 - 6, 60, alto_vara, p)
        x = MARGEN + 120
        d.text((x, top + 8), p["puerto"], font=_archivo(46, 800, 88), fill=CARBON)
        estado = NIVEL_TXT[p["nivel"]].capitalize()
        f = _archivo(32, 700, 95)
        d.text((x, top + 64), estado, font=f, fill=COLOR[p["nivel"]])
        d.text((x + f.getlength(estado) + 14, top + 64), f"· {metros(p['altura'])}, {frase_puerto(p)}",
               font=_archivo(30, 500, 95), fill=CARBON_SUAVE)
    return img


def costa(r: Resumen, ahora: datetime) -> Image.Image:
    img, d = _marco(3, 3, ahora)
    y = 170
    ancho = ANCHO - 2 * MARGEN
    for zona, nivel, estado, frase in (
        ("Buenos Aires y el Delta", r.costa_nivel, NIVEL_TXT.get(r.costa_nivel, "sin datos"), r.costa_frase),
        ("Lluvia y tormentas · AMBA", r.lluvia_nivel, SMN_TXT.get(r.lluvia_nivel, "sin datos"), r.lluvia_frase),
    ):
        f_frase = _archivo(40, 500, 100)
        alto = 190 + len(_lineas(frase, f_frase, ancho - 80)) * 48
        d.rounded_rectangle([MARGEN, y, MARGEN + ancho, y + alto], radius=10, fill=SUPERFICIE, outline=LINEA, width=2)
        d.rectangle([MARGEN, y, MARGEN + ancho, y + 16], fill=COLOR.get(nivel, COLOR["sin"]))
        d.text((MARGEN + 40, y + 50), zona.upper(), font=_mono(28), fill=CARBON_SUAVE)
        d.text((MARGEN + 40, y + 92), estado.upper(), font=_archivo(52, 800, 82), fill=COLOR.get(nivel, COLOR["sin"]))
        _parrafo(d, (MARGEN + 40, y + 165), frase, f_frase, ancho - 80)
        y += alto + 40
    caja = ALTO - 190 - 200
    if y <= caja:
        d.rounded_rectangle([MARGEN, caja, ANCHO - MARGEN, caja + 170], radius=10, fill=CARTEL)
        d.text((MARGEN + 40, caja + 34), "¿Cómo está el agua en tu ciudad?", font=_archivo(44, 800, 85), fill=CARTEL_TEXTO)
        d.text((MARGEN + 40, caja + 100), URL, font=_mono(30), fill=CARTEL_TEXTO)
    return img


def carrusel(r: Resumen, ahora: datetime) -> list[Image.Image]:
    return [portada(r, ahora), puertos(r, ahora), costa(r, ahora)]
