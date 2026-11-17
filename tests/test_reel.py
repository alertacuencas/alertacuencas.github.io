import json
from datetime import datetime, timezone

import pytest
from PIL import Image

from alertas.reel import guion as g
from alertas.reel import numeros, salida, tiempos

# 13:00 UTC = 10:00 hora argentina del 17/11
AHORA = datetime(2026, 11, 17, 13, 0, tzinfo=timezone.utc)


def _puerto(nombre, nivel, exceso=0.1, alerta=5.3, evac=5.7, rio="PARANAINF", ts="2026-11-17T03:00:00Z"):
    alturas = {"evacuacion": evac + exceso, "alerta": evac - exceso, "normal": alerta - 0.4}
    return {"puerto": nombre, "rio": rio, "altura": round(alturas[nivel], 2), "variacion": 0.0, "ts": ts,
            "alerta": alerta, "evacuacion": evac, "nivel": nivel, "tendencia": "estable", "viejo": False,
            "lat": -31.0, "lon": -60.0}


def _parana(*puertos):
    return {"version": 1, "puertos": list(puertos)}


def _estado(nivel="verde", expira="2026-11-17T20:00:00+00:00"):
    alertas = [] if nivel == "verde" else [{"evento": "Tormentas", "nivel": nivel, "expira": expira, "descripcion": "x"}]
    return {"version": 1, "zonas": {"medrano": {"nombre": "Arroyo Medrano", "nivel_smn": nivel, "alertas": alertas}}}


EVAC = _parana(
    _puerto("Corrientes", "alerta", 0.5, evac=7.0, alerta=6.5),
    _puerto("Goya", "evacuacion", 0.11),
    _puerto("Paraná", "evacuacion", 0.69, evac=5.0, alerta=4.7),
    _puerto("Diamante", "evacuacion", 0.32),
    _puerto("Rosario", "normal"),
    _puerto("San Fernando", "normal", rio="PARANADELASPALMAS"),
)


# ---------- números en letras ----------

@pytest.mark.parametrize("n, texto", [
    (0, "cero"), (1, "uno"), (8, "ocho"), (15, "quince"), (21, "veintiuno"), (22, "veintidós"),
    (30, "treinta"), (69, "sesenta y nueve"), (100, "cien"), (103, "ciento tres"), (250, "doscientos cincuenta"),
    (999, "novecientos noventa y nueve"),
])
def test_en_letras(n, texto):
    assert numeros.en_letras(n) == texto


def test_en_letras_femenino_para_ciudades():
    assert numeros.en_letras(1, femenino=True) == "una"
    assert numeros.en_letras(21, femenino=True) == "veintiuna"


@pytest.mark.parametrize("metros, voz, sub", [
    (0.69, "sesenta y nueve centímetros", "69 cm"),
    (0.07, "siete centímetros", "7 cm"),
    (1.0, "un metro", "1 m"),
    (1.25, "un metro con veinticinco centímetros", "1,25 m"),
    (2.4, "dos metros con cuarenta centímetros", "2,40 m"),
])
def test_distancias(metros, voz, sub):
    assert numeros.distancia_voz(metros) == voz
    assert numeros.distancia_sub(metros) == sub


# ---------- guion ----------

def test_guion_con_ciudades_en_evacuacion():
    gu = g.armar(EVAC, _estado(), None, AHORA)
    voz = gu.texto_voz
    assert voz.startswith("Hoy, tres ciudades del Paraná están en evacuación. Desde Goya hasta Diamante. Otra, en alerta.")
    assert "En Buenos Aires y el Delta, el río está tranquilo." in voz
    assert "¿Y en tu ciudad?" in voz
    # la ciudad de ejemplo es la que más pasó el nivel de evacuación
    assert gu.ciudad == "Paraná"
    assert "En la ciudad de Paraná, el agua está sesenta y nueve centímetros por encima del nivel de evacuación." in voz
    assert voz.endswith("No somos un sistema oficial: ante una emergencia, Defensa Civil, ciento tres. Seguí a Alerta Cuencas.")
    assert not any(c.isdigit() for c in voz)  # la voz va con números en letras


def test_subtitulos_con_numeros_y_cortos():
    gu = g.armar(EVAC, _estado(), None, AHORA)
    subs = [s for b in gu.bloques for s in b.subs]
    assert "Hoy, 3 ciudades del Paraná están en evacuación" in subs
    assert any("69 cm por encima del nivel de evacuación" in s for s in subs)
    assert all(len(s) <= 80 for s in subs)


def test_claves_de_bloques_en_orden():
    gu = g.armar(EVAC, _estado(), None, AHORA)
    assert [b.clave for b in gu.bloques] == ["hoy", "costa", "tuCiudad", "ciudad", "rio", "noOficial", "fin"]


def test_sin_evacuacion_usa_alerta():
    p = _parana(_puerto("Corrientes", "alerta", 0.4, evac=7.0, alerta=6.5), _puerto("Rosario", "normal"))
    gu = g.armar(p, _estado(), None, AHORA)
    assert gu.texto_voz.startswith("Hoy, el Paraná está en alerta en Corrientes.")
    assert gu.ciudad == "Corrientes"
    assert "En Corrientes, el agua está a cuarenta centímetros del nivel de evacuación." in gu.texto_voz


def test_todo_normal():
    p = _parana(_puerto("Rosario", "normal"), _puerto("Santa Fe", "normal"))
    gu = g.armar(p, _estado(), None, AHORA)
    assert gu.texto_voz.startswith("Hoy, el Paraná está normal en todos los puertos.")


def test_alerta_smn_vigente_se_menciona_y_la_vencida_no():
    vigente = g.armar(EVAC, _estado("naranja"), None, AHORA)
    assert "El Servicio Meteorológico tiene alerta naranja por tormentas en el AMBA." in vigente.texto_voz
    vencida = g.armar(EVAC, _estado("amarillo", expira="2026-11-17T11:59:59+00:00"), None, AHORA)
    assert "Servicio Meteorológico" not in vencida.texto_voz
    assert "alerta amarilla" not in vencida.titular_portada


def test_aviso_si_la_lectura_no_es_de_hoy():
    viejo = _parana(_puerto("Paraná", "evacuacion", 0.69, ts="2026-11-16T03:00:00Z"))
    gu = g.armar(viejo, _estado(), None, AHORA)
    assert any("16/11" in a for a in gu.avisos)
    assert g.armar(EVAC, _estado(), None, AHORA).avisos == ()


def test_posteo_y_portada():
    gu = g.armar(EVAC, _estado(), None, AHORA)
    assert "alertacuencas.github.io (link en el perfil)" in gu.posteo
    assert "Defensa Civil 103" in gu.posteo
    assert gu.titular_portada == "El Paraná está en evacuación en 3 ciudades. En Buenos Aires y el Delta, el río está tranquilo."


# ---------- tiempos ----------

def _palabras(texto, paso=0.3):
    return [(w, round(i * paso, 2)) for i, w in enumerate(texto.split())]


def test_tiempos_alinea_cada_bloque_con_la_transcripcion():
    gu = g.armar(EVAC, _estado(), None, AHORA)
    # Whisper escribe los números con cifras: no tiene que importar
    transcripto = gu.texto_voz.replace("tres ciudades", "3 ciudades").replace("ciento tres", "103")
    palabras = _palabras(transcripto)
    t, subs = tiempos.calcular(gu, palabras, duracion=palabras[-1][1] + 0.5)
    inicio = {w: s for w, s in palabras}
    assert t["costa"] == pytest.approx(next(s for w, s in palabras if w == "Buenos") - 0.3)
    assert t["tuCiudad"] == inicio["¿Y"]
    assert t["rio"] == inicio["Acá"]
    assert t["noOficial"] == inicio["No"]
    assert t["fin"] == inicio["Seguí"]
    assert subs[0][0] == 0.0
    # los subtítulos son consecutivos y terminan donde arranca la placa final
    for (a, b, _), (c, _, _) in zip(subs, subs[1:]):
        assert b == pytest.approx(c)
    assert subs[-1][1] == pytest.approx(t["fin"])


def test_tiempos_sin_ancla_reparte_por_largo():
    gu = g.armar(EVAC, _estado(), None, AHORA)
    t, subs = tiempos.calcular(gu, [("hola", 0.0)], duracion=25.0)
    assert 0 < t["costa"] < t["tuCiudad"] < t["ciudad"] < t["rio"] < t["noOficial"] < t["fin"] < 25.0


# ---------- salida ----------

def test_reel_dia_js(tmp_path):
    gu = g.armar(EVAC, _estado(), None, AHORA)
    t, subs = tiempos.calcular(gu, [], duracion=25.0)
    ruta = salida.reel_dia_js(tmp_path, gu, t, subs)
    js = ruta.read_text()
    assert js.startswith("// Reel del 17/11/2026")
    datos = json.loads(js.split("window.REEL = ", 1)[1].rstrip().rstrip(";"))
    assert datos["CIUDAD"] == "Paraná"
    assert set(datos["T"]) == {"costa", "tuCiudad", "ciudad", "rio", "noOficial", "fin"}
    assert len(datos["SUBS"]) == len(subs)


def test_preparar_escribe_los_archivos_del_dia(tmp_path):
    gu = g.armar(EVAC, _estado(), None, AHORA)
    rutas = salida.preparar(tmp_path, gu, AHORA)
    nombres = {r.name for r in rutas}
    assert {"guion.md", "texto-voz.txt", "posteo.txt", "portada.png"} <= nombres
    assert (tmp_path / "texto-voz.txt").read_text().strip() == gu.texto_voz
    assert Image.open(tmp_path / "portada.png").size == (1080, 1920)
    md = (tmp_path / "guion.md").read_text()
    assert md.startswith("# Reel 17/11/2026")
    assert gu.texto_voz in md


# ---------- casos de la revisión ----------

@pytest.mark.parametrize("metros, voz", [
    (0.01, "un centímetro"),
    (0.21, "veintiún centímetros"),
    (0.31, "treinta y un centímetros"),
    (1.01, "un metro con un centímetro"),
    (21.0, "veintiún metros"),
])
def test_distancias_con_apocope(metros, voz):
    assert numeros.distancia_voz(metros) == voz


def test_justo_en_el_nivel_de_evacuacion():
    p = _parana(_puerto("Goya", "evacuacion", 0.0))
    assert "En Goya, el agua está justo en el nivel de evacuación." in g.armar(p, _estado(), None, AHORA).texto_voz


def test_costa_sin_datos_no_dice_tranquilo():
    p = _parana(_puerto("Goya", "evacuacion", 0.2))  # ningún puerto del Delta y sin serie
    gu = g.armar(p, _estado(), None, AHORA)
    assert "el río está tranquilo" not in gu.texto_voz
    assert "No hay lecturas recientes del Delta." in gu.texto_voz
    assert "tranquilo" not in gu.titular_portada
    assert any("Delta" in a for a in gu.avisos)


def _serie(residuo, ts):
    return {"estaciones": {"SFER": {"residuo": [[ts, residuo]]}}}


def test_sudestada_reciente_se_menciona_y_la_vieja_no():
    delta = _puerto("San Fernando", "normal", rio="PARANADELASPALMAS")
    p = _parana(_puerto("Goya", "evacuacion", 0.2), delta)
    reciente = g.armar(p, _estado(), _serie(0.8, "2026-11-17T12:30:00+00:00"), AHORA)
    assert "En San Fernando, el río está ochenta centímetros más alto que la marea" in reciente.texto_voz
    vieja = g.armar(p, _estado(), _serie(0.8, "2026-11-16T12:30:00+00:00"), AHORA)
    assert "ochenta centímetros" not in vieja.texto_voz


def test_nombres_de_puertos_limpios_en_la_voz():
    p = _parana(_puerto("San Lorenzo (San Martín)", "evacuacion", 0.2), _puerto("Paraná", "evacuacion", 0.1))
    voz = g.armar(p, _estado(), None, AHORA).texto_voz
    assert "(" not in voz
    assert "Desde San Lorenzo hasta la ciudad de Paraná." in voz


def test_guion_se_guarda_y_se_recupera_igual(tmp_path):
    gu = g.armar(EVAC, _estado("naranja"), None, AHORA)
    ruta = salida.guardar_guion(tmp_path, gu)
    assert g.cargar(ruta) == gu


def test_ancla_del_segundo_bloque_no_cae_dentro_del_primero():
    # el bloque de la costa con alerta en el Delta arranca con "En el", que también podría aparecer antes
    delta = _puerto("Tigre", "alerta", 0.2, rio="PARANADELASPALMAS")
    p = _parana(_puerto("Goya", "evacuacion", 0.2), delta)
    gu = g.armar(p, _estado(), None, AHORA)
    palabras = _palabras("Hoy, una ciudad en el Paraná está en evacuación: Goya. " + " ".join(b.voz for b in gu.bloques[1:]))
    t, _ = tiempos.calcular(gu, palabras, duracion=palabras[-1][1] + 0.5)
    costa = next(i for i, (w, _) in enumerate(palabras) if w == "Delta,") - 2
    assert t["costa"] == palabras[costa][1]
