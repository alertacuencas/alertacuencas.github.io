import json
from datetime import datetime, timedelta, timezone

from PIL import Image

from alertas import publicar
from alertas.publicar import imagenes, reglas, resumen

# 13:00 UTC = 10:00 hora argentina
AHORA = datetime(2026, 11, 16, 13, 0, tzinfo=timezone.utc)
MADRUGADA = datetime(2026, 11, 16, 6, 0, tzinfo=timezone.utc)  # 03:00 ART


def _puerto(nombre, nivel, altura=5.0, alerta=5.3, evac=5.7, rio="PARANAINF", viejo=False):
    alturas = {"evacuacion": evac + 0.1, "alerta": (alerta + evac) / 2, "normal": alerta - 0.4}
    return {"puerto": nombre, "rio": rio, "altura": alturas.get(nivel, altura), "variacion": 0.0,
            "ts": "2026-11-16T03:00:00Z", "alerta": alerta, "evacuacion": evac, "nivel": nivel,
            "tendencia": "estable", "viejo": viejo, "lat": -31.0, "lon": -60.0}


def _parana(*puertos):
    return {"version": 1, "puertos": list(puertos)}


def _estado(**zonas):
    return {"version": 1, "zonas": {
        zid: {"nombre": zid.title(), "nivel_smn": nivel,
              "alertas": [] if nivel == "verde" else [{"evento": "Tormentas", "nivel": nivel,
                                                     "expira": "2026-11-17T12:00:00+00:00", "descripcion": "x"}]}
        for zid, nivel in zonas.items()}}


SERIE = {"estaciones": {"SFER": {"residuo": [["2026-11-16T12:45:00+00:00", 0.15]]}}}


# ── Resumen ──

def test_resumen_con_evacuacion_alerta_y_tormentas():
    r = resumen.armar(
        _parana(_puerto("Goya", "evacuacion"), _puerto("Santa Fe", "evacuacion"), _puerto("Rosario", "alerta"),
                _puerto("Zárate", "normal", rio="PARANADELASPALMAS"), _puerto("Viejo", "evacuacion", viejo=True)),
        _estado(medrano="amarillo", lujan="verde"), SERIE)

    assert r.titular == ("El Paraná está en evacuación en 2 ciudades. En Buenos Aires y el Delta, "
                         "el río está tranquilo. Hay alerta amarilla por tormentas en el AMBA.")
    assert r.evacuacion == ["Goya", "Santa Fe"], "las lecturas viejas no cuentan"
    assert [p["puerto"] for p in r.afectados][:3] == ["Goya", "Santa Fe", "Rosario"]
    assert "15 cm más alta" in r.costa_frase and "Ninguna escala del Delta" in r.costa_frase
    assert r.lluvia_nivel == "amarillo" and r.zonas_fuertes == []


def test_resumen_sin_datos_no_inventa():
    r = resumen.armar(None, None, None)
    assert r.nivel_parana == "sin" and r.afectados == []
    assert r.costa_frase == "Sin datos recientes del río."
    assert r.lluvia_nivel == "sin"


def test_resumen_delta_en_alerta_y_smn_naranja():
    r = resumen.armar(_parana(_puerto("Campana", "alerta", rio="PARANADELASPALMAS")),
                      _estado(riachuelo="naranja"), None)
    assert "Atención en el Delta." in r.titular
    assert r.costa_nivel == "alerta" and "Campana en alerta" in r.costa_frase
    assert r.zonas_fuertes == ["riachuelo"]


def test_distancias_en_lenguaje_claro():
    assert resumen.distancia(0.07) == "7 cm"
    assert resumen.distancia(-1.2) == "1,20 m"
    assert resumen.enumerar(["A", "B", "C"]) == "A, B y C"


# ── Reglas ──

def test_primera_corrida_de_la_manana_publica_el_resumen_diario():
    d, mem = reglas.decidir(["Goya"], [], {}, AHORA)
    assert (d.publicar, d.motivo) == (True, "diario")
    assert mem["ultimo_diario"] == "2026-11-16"

    d2, _ = reglas.decidir(["Goya"], [], mem, AHORA + timedelta(minutes=10))
    assert (d2.publicar, d2.motivo) == (False, "sin_novedad"), "un solo resumen por día"


def test_de_madrugada_no_hay_resumen_diario():
    d, mem = reglas.decidir([], [], {}, MADRUGADA)
    assert d.publicar is False
    assert mem["ultimo_diario"] is None


def test_un_puerto_que_entra_en_evacuacion_publica_aunque_ya_hubo_resumen():
    _, mem = reglas.decidir(["Goya"], [], {}, AHORA)
    d, _ = reglas.decidir(["Goya", "Santa Fe"], [], mem, AHORA + timedelta(hours=1))
    assert (d.publicar, d.motivo) == (True, "cambio")
    assert d.detalle == "Santa Fe entró en nivel de evacuación."


def test_un_puerto_que_sale_de_evacuacion_tambien_es_noticia():
    _, mem = reglas.decidir(["Goya", "Santa Fe"], [], {}, AHORA)
    d, _ = reglas.decidir(["Goya"], [], mem, AHORA + timedelta(hours=1))
    assert d.detalle == "Santa Fe salió del nivel de evacuación."


def test_alerta_naranja_nueva_del_smn():
    _, mem = reglas.decidir([], [], {}, AHORA)
    d, _ = reglas.decidir([], ["riachuelo"], mem, AHORA + timedelta(hours=1))
    assert d.motivo == "cambio" and "alerta naranja o roja" in d.detalle


def test_fuente_caida_no_se_toma_como_que_todo_volvio_a_la_normalidad():
    _, mem = reglas.decidir(["Goya"], ["riachuelo"], {}, AHORA)
    d, mem2 = reglas.decidir(None, None, mem, AHORA + timedelta(hours=1))
    assert d.publicar is False
    assert mem2["vista"] == {"evacuacion": ["Goya"], "zonas_fuertes": ["riachuelo"]}


def test_tope_de_publicaciones_por_dia():
    mem, evac = {}, []
    publicadas = 0
    for i in range(8):  # un puerto nuevo en evacuación cada hora
        evac = [*evac, f"P{i}"]
        d, mem = reglas.decidir(evac, [], mem, AHORA + timedelta(hours=i))
        publicadas += d.publicar
    assert publicadas == reglas.MAX_POR_DIA
    assert d.motivo == "tope"


def test_cambio_de_madrugada_no_reemplaza_el_resumen_de_las_8():
    _, mem = reglas.decidir([], [], {}, MADRUGADA)
    d, mem = reglas.decidir(["Goya"], [], mem, MADRUGADA + timedelta(hours=1))
    assert d.motivo == "cambio"
    d, _ = reglas.decidir(["Goya"], [], mem, AHORA)
    assert d.motivo == "diario"


def test_la_memoria_no_se_modifica_y_guarda_historial():
    mem = {}
    _, nueva = reglas.decidir([], [], mem, AHORA)
    assert mem == {}
    assert nueva["historial"][0]["motivo"] == "diario"


# ── Epígrafe, imágenes y procesar ──

def test_epigrafe_pone_lo_nuevo_primero_y_el_aviso():
    r = resumen.armar(_parana(_puerto("Santa Fe", "evacuacion")), _estado(medrano="verde"), SERIE)
    texto = publicar.epigrafe(r, reglas.Decision(True, "cambio", "Santa Fe entró en nivel de evacuación."), AHORA)
    assert texto.startswith("Santa Fe entró en nivel de evacuación.")
    assert "🔴 En evacuación: Santa Fe." in texto
    assert publicar.AVISO in texto and publicar.URL_WEB in texto
    assert len(texto) <= 2200, "límite de Instagram"


def test_carrusel_tres_imagenes_del_tamano_de_instagram():
    r = resumen.armar(_parana(*[_puerto(f"Puerto {i}", "evacuacion") for i in range(9)]), _estado(a="rojo"), SERIE)
    imgs = imagenes.carrusel(r, AHORA)
    assert [i.size for i in imgs] == [(1080, 1350)] * 3
    assert all(len(i.getcolors(1_000_000)) > 10 for i in imgs), "no deben salir en blanco"


def test_carrusel_sin_datos_no_rompe():
    imgs = imagenes.carrusel(resumen.armar(None, None, None), AHORA)
    assert len(imgs) == 3


def test_procesar_deja_la_publicacion_para_revisar(tmp_path):
    memoria, salida = tmp_path / "mem.json", tmp_path / "pub"
    d = publicar.procesar(_parana(_puerto("Goya", "evacuacion")), _estado(medrano="verde"), SERIE,
                          memoria, salida, AHORA)

    pub = json.loads((salida / "publicacion.json").read_text())
    assert d.publicar and pub["modo"] == "prueba" and pub["motivo"] == "diario"
    assert pub["imagenes"] == ["1.png", "2.png", "3.png"]
    assert Image.open(salida / "1.png").size == (1080, 1350)
    assert json.loads(memoria.read_text())["vista"]["evacuacion"] == ["Goya"]

    d2 = publicar.procesar(_parana(_puerto("Goya", "evacuacion")), _estado(medrano="verde"), SERIE,
                           memoria, salida, AHORA + timedelta(minutes=10))
    assert d2.publicar is False
    assert len(json.loads((salida / "publicacion.json").read_text())["historial"]) == 2


def test_procesar_con_memoria_corrupta_arranca_de_cero(tmp_path):
    memoria = tmp_path / "mem.json"
    memoria.write_text("{no es json")
    d = publicar.procesar(None, None, None, memoria, tmp_path / "pub", AHORA)
    assert d.motivo == "diario"
