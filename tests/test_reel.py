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
    # solo lo crítico: sin rango de ciudades, sin las de alerta y sin la costa tranquila
    assert voz.startswith("Hoy, tres ciudades del Paraná están en evacuación. ¿Dónde está más complicado?")
    assert "Desde" not in voz and "tranquilo" not in voz and "alerta" not in voz
    # la ficha es la que más pasó el nivel de evacuación, y después las que siguen
    assert gu.ciudad == "Paraná"
    assert ("En la ciudad de Paraná, el agua está sesenta y nueve centímetros por encima del nivel de evacuación. "
            "En Diamante, treinta y dos centímetros. Y en Goya, once centímetros.") in voz
    assert "Acá está todo el Paraná. Por ahora, el río se mantiene estable." in voz
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
    assert [b.clave for b in gu.bloques] == ["hoy", "tuCiudad", "ciudad", "rio", "noOficial", "fin"]
    sin_evac = g.armar(_parana(_puerto("Rosario", "normal")), _estado(), None, AHORA)
    assert [b.clave for b in sin_evac.bloques] == ["hoy", "costa", "tuCiudad", "ciudad", "rio", "noOficial", "fin"]


def _evac(nombre, exceso, tendencia="estable"):
    return _puerto(nombre, "evacuacion", exceso) | {"tendencia": tendencia}


def test_evacuacion_nombra_las_cuatro_peores_y_despues_el_resto():
    p = _parana(_evac("Goya", 0.06), _evac("San Javier (Santa Fe)", 1.34), _evac("Paraná", 0.71),
                _evac("Hernandarias", 0.42), _evac("Diamante", 0.35), _evac("Reconquista", 0.29),
                _evac("Santa Fe", 0.16), _puerto("Victoria", "alerta", 0.14))
    gu = g.armar(p, _estado(), None, AHORA)
    assert gu.ciudad == "San Javier (Santa Fe)"
    ciudad = next(b for b in gu.bloques if b.clave == "ciudad")
    assert ciudad.voz == ("En San Javier, el agua está un metro con treinta y cuatro centímetros por encima del nivel de "
                          "evacuación. En la ciudad de Paraná, setenta y un centímetros. En Hernandarias, cuarenta y dos "
                          "centímetros. Y en Diamante, treinta y cinco centímetros.")
    assert "En Paraná, 71 cm" in " ".join(ciudad.subs)
    rio = next(b for b in gu.bloques if b.clave == "rio")
    assert rio.voz == "Reconquista, Santa Fe y Goya también pasaron el nivel de evacuación. Por ahora, el río se mantiene estable."
    assert gu.texto_voz.startswith("Hoy, siete ciudades del Paraná están en evacuación.")
    assert "Victoria" not in gu.texto_voz
    assert "Lo más grave: San Javier (+1,34 m), Paraná (+71 cm), Hernandarias (+42 cm) y Diamante (+35 cm)." in gu.posteo


@pytest.mark.parametrize("tendencias, frase", [
    (["sube", "sube", "estable"], "En la mayoría, el río sigue subiendo."),
    (["baja", "baja", "sube"], "En la mayoría, el río ya empieza a bajar."),
    (["estable", "estable", "sube"], "Por ahora, el río se mantiene estable."),
    (["sube", "baja", "estable"], ""),
])
def test_tendencia_de_las_ciudades_en_evacuacion(tendencias, frase):
    p = _parana(*(_evac(n, 0.1 * (i + 1), t) for i, (n, t) in enumerate(zip(["Goya", "Esquina", "La Paz"], tendencias))))
    rio = next(b for b in g.armar(p, _estado(), None, AHORA).bloques if b.clave == "rio")
    assert rio.voz.endswith(frase or "Acá está todo el Paraná.")


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
    assert gu.titular_portada == "El Paraná está en evacuación en 3 ciudades."
    assert "tranquilo" not in gu.posteo
    assert gu.costa_nivel == ""  # la portada tampoco muestra la costa


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
    assert t["tuCiudad"] == inicio["¿Dónde"]
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
    assert 0 < t["tuCiudad"] < t["ciudad"] < t["rio"] < t["noOficial"] < t["fin"] < 25.0


# ---------- salida ----------

def test_reel_dia_js(tmp_path):
    gu = g.armar(EVAC, _estado(), None, AHORA)
    t, subs = tiempos.calcular(gu, [], duracion=25.0)
    ruta = salida.reel_dia_js(tmp_path, gu, t, subs)
    js = ruta.read_text()
    assert js.startswith("// Reel del 17/11/2026")
    datos = json.loads(js.split("window.REEL = ", 1)[1].rstrip().rstrip(";"))
    assert datos["CIUDAD"] == "Paraná"
    assert set(datos["T"]) == {"tuCiudad", "ciudad", "rio", "noOficial", "fin"}
    assert len(datos["SUBS"]) == len(subs)


def test_preparar_escribe_los_archivos_del_dia(tmp_path):
    gu = g.armar(EVAC, _estado(), None, AHORA)
    rutas = salida.preparar(tmp_path, gu, AHORA)
    nombres = {r.name for r in rutas}
    assert {"guion.md", "texto-voz.txt", "posteo.txt", "portada.png"} <= nombres
    assert (tmp_path / "texto-voz.txt").read_text().strip() == gu.texto_voz
    assert Image.open(tmp_path / "portada.png").size == (1080, 1920)
    con_costa = g.armar(_parana(_puerto("Rosario", "normal")), _estado(), None, AHORA)
    salida.preparar(tmp_path / "otra", con_costa, AHORA)
    assert Image.open(tmp_path / "otra" / "portada.png").size == (1080, 1920)
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
    p = _parana(_puerto("Goya", "alerta", 0.2))  # ningún puerto del Delta y sin serie
    gu = g.armar(p, _estado(), None, AHORA)
    assert "el río está tranquilo" not in gu.texto_voz
    assert "No hay lecturas recientes del Delta." in gu.texto_voz
    assert "tranquilo" not in gu.titular_portada
    assert any("Delta" in a for a in gu.avisos)


def _serie(residuo, ts):
    return {"estaciones": {"SFER": {"residuo": [[ts, residuo]]}}}


def test_sudestada_reciente_se_menciona_y_la_vieja_no():
    delta = _puerto("San Fernando", "normal", rio="PARANADELASPALMAS")
    p = _parana(_puerto("Goya", "alerta", 0.2), delta)
    reciente = g.armar(p, _estado(), _serie(0.8, "2026-11-17T12:30:00+00:00"), AHORA)
    assert "En San Fernando, el río está ochenta centímetros más alto que la marea" in reciente.texto_voz
    # con ciudades del Paraná en evacuación, la sudestada no entra: el reel habla solo de lo crítico
    con_evac = g.armar(_parana(_puerto("Goya", "evacuacion", 0.2), delta), _estado(), _serie(0.8, "2026-11-17T12:30:00+00:00"), AHORA)
    assert "San Fernando" not in con_evac.texto_voz
    vieja = g.armar(p, _estado(), _serie(0.8, "2026-11-16T12:30:00+00:00"), AHORA)
    assert "ochenta centímetros" not in vieja.texto_voz


def test_nombres_de_puertos_limpios_en_la_voz():
    p = _parana(_puerto("San Lorenzo (San Martín)", "evacuacion", 0.2), _puerto("Paraná", "evacuacion", 0.1))
    voz = g.armar(p, _estado(), None, AHORA).texto_voz
    assert "(" not in voz
    assert "En San Lorenzo, el agua está" in voz


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


def test_subtitulos_arrancan_cuando_la_voz_dice_su_frase():
    # la primera frase del bloque se lee más lenta: el reparto por largo atrasaría a las siguientes
    p = _parana(_evac("San Javier (Santa Fe)", 1.34), _evac("Paraná", 0.71), _evac("Hernandarias", 0.42),
                _evac("Diamante", 0.35))
    gu = g.armar(p, _estado(), None, AHORA)
    palabras, t = [], 0.0
    for w in gu.texto_voz.split():
        palabras.append((w, round(t, 2)))
        t += 0.8 if len(palabras) < 25 else 0.3
    tt, subs = tiempos.calcular(gu, palabras, duracion=t + 0.5)
    inicio = {s: a for a, _, s in subs}
    en_parana = next(i for i, (w, _) in enumerate(palabras) if w == "ciudad") - 2
    assert inicio["En Paraná, 71 cm. En Hernandarias, 42 cm"] == palabras[en_parana][1]
    y_en = next(i for i, (w, _) in enumerate(palabras) if w == "Diamante,") - 2
    assert inicio["Y en Diamante, 35 cm"] == palabras[y_en][1]
    for (a, b, _), (c, _, _) in zip(subs, subs[1:]):
        assert b == pytest.approx(c)


def _siete():
    return _parana(_evac("Goya", 0.06), _evac("San Javier (Santa Fe)", 1.34), _evac("Paraná", 0.71),
                   _evac("Hernandarias", 0.42), _evac("Diamante", 0.35), _evac("Reconquista", 0.29),
                   _evac("Santa Fe", 0.16))


def test_fichas_son_las_ciudades_que_nombra_la_voz():
    gu = g.armar(_siete(), _estado(), None, AHORA)
    assert gu.fichas == ("San Javier (Santa Fe)", "Paraná", "Hernandarias", "Diamante")
    normal = g.armar(_parana(_puerto("Rosario", "normal")), _estado(), None, AHORA)
    assert normal.fichas == ("Rosario",)


def test_cada_ficha_aparece_cuando_la_voz_nombra_su_ciudad(tmp_path):
    gu = g.armar(_siete(), _estado(), None, AHORA)
    palabras = _palabras(gu.texto_voz)
    t, subs = tiempos.calcular(gu, palabras, duracion=palabras[-1][1] + 0.5)
    fichas = tiempos.fichas(gu, palabras, t)
    assert [p for _, p in fichas] == list(gu.fichas)
    assert fichas[0][0] == t["ciudad"]
    en_la = next(i for i, (w, _) in enumerate(palabras) if w == "ciudad" and palabras[i + 2][0].startswith("Paraná")) - 2
    assert fichas[1][0] == palabras[en_la][1]
    js = salida.reel_dia_js(tmp_path, gu, t, subs, fichas).read_text()
    datos = json.loads(js.split("window.REEL = ", 1)[1].rstrip().rstrip(";"))
    assert datos["FICHAS"] == [[a, p] for a, p in fichas]


def test_fichas_sin_transcripcion_queda_solo_la_primera():
    gu = g.armar(_siete(), _estado(), None, AHORA)
    t, _ = tiempos.calcular(gu, [("hola", 0.0)], duracion=30.0)
    assert tiempos.fichas(gu, [("hola", 0.0)], t) == [(t["ciudad"], "San Javier (Santa Fe)")]


def _rio(cuenca, puerto):
    return puerto | {"cuenca": cuenca}


def test_varios_rios_en_evacuacion_de_lo_mas_grave_a_lo_menos():
    p = _parana(_evac("Santa Fe", 0.5), _evac("Rosario", 0.2), _rio("Uruguay", _evac("San Javier", 0.9)),
                _rio("Paraguay", _puerto("Isla del Cerrito", "alerta", 0.3)), _puerto("Goya", "alerta", 0.1))
    gu = g.armar(p, _estado(), None, AHORA)
    b = {x.clave: x for x in gu.bloques}
    assert b["hoy"].voz == "Hoy, tres ciudades están en evacuación: una sobre el Uruguay y dos sobre el Paraná."
    assert b["ciudad"].voz.startswith("En San Javier, sobre el Uruguay, el agua está")
    assert gu.fichas == ("San Javier", "Santa Fe", "Rosario")
    assert b["rio"].voz.endswith("Además, el Paraguay está en alerta."), "el Paraná ya se nombró por su evacuación"
    assert gu.titular_portada.startswith("El Uruguay está en evacuación en 1 ciudad y el Paraná en 2. "
                                         "El Paraguay está en alerta en 1 ciudad.")
    assert "San Javier, sobre el Uruguay (+90 cm)" in gu.posteo


def test_solo_alerta_en_otro_rio():
    p = _parana(_puerto("Santa Fe", "normal"), _rio("Paraguay", _puerto("Isla del Cerrito", "alerta", 0.3)))
    gu = g.armar(p, _estado(), None, AHORA)
    b = {x.clave: x for x in gu.bloques}
    assert b["hoy"].voz == "Hoy, el Paraguay está en alerta en Isla del Cerrito."
    assert b["ciudad"].voz.startswith("En Isla del Cerrito, sobre el Paraguay,")
    assert b["rio"].voz == "Acá están todos los ríos, de lo más grave a lo más tranquilo."
