from datetime import datetime, timezone

import pytest

from alertas.fuentes import prefectura

AHORA = datetime(2026, 11, 16, 15, 0, tzinfo=timezone.utc)


def _fila(puerto="SANTA FE", rio="PARANA", altura="5.78", var="0.01",
          fecha="16/NOV/26 - 1000", alerta="5.30", evac="5.70"):
    return f"""<table><tr>
      <th data-label="Puerto:">{puerto}</th><td data-label="Río:">{rio}</td>
      <td data-label="Ultimo Registro:" class="warning">{altura}</td>
      <td data-label="Variacion">{var}</td><td data-label="Periodo">2</td>
      <td data-label="Fecha Hora:"><b>{fecha}</b></td><td data-label="Estado:">X</td>
      <td><img src="x.svg"></td>
      <td data-label="Alerta:">{alerta}</td><td data-label="Evacuación:">{evac}</td>
    </tr></table>"""


def _por_nombre(html):
    return {p.puerto: p for p in prefectura.parse(html, AHORA)}


def test_parsea_la_tabla_real_del_16_de_noviembre(fixture_text):
    puertos = _por_nombre(fixture_text("pna_alturas_16nov.html"))

    santa_fe = puertos["Santa Fe"]
    assert santa_fe.altura == 5.78
    assert (santa_fe.alerta, santa_fe.evacuacion) == (5.30, 5.70)
    assert santa_fe.nivel == "evacuacion"
    assert santa_fe.tendencia == "estable"  # +0,01 m en 2 h
    assert santa_fe.ts == "2026-11-16T13:00:00Z"  # 10:00 hora argentina
    assert puertos["Rosario"].nivel == "normal"
    assert puertos["San Lorenzo"].nivel == "alerta"
    assert puertos["San Javier (Santa Fe)"].nivel == "evacuacion"
    assert puertos["San Fernando"].rio == "DELTA PARANA"
    assert puertos["Paraná"].nivel == "evacuacion"
    assert "Zárate" in puertos
    assert "Paso de la Patria" in puertos


def test_deja_afuera_otros_rios_y_puertos_sin_umbral(fixture_text):
    puertos = prefectura.parse(fixture_text("pna_alturas_16nov.html"), AHORA)

    assert {p.rio for p in puertos} <= prefectura.RIOS
    assert all(p.altura < 30 for p in puertos), "las represas sin umbral (150 m) no entran"
    assert "Buenos Aires" not in {p.puerto for p in puertos}  # río de la Plata


def test_conserva_el_orden_de_aguas_arriba_hacia_el_delta(fixture_text):
    nombres = [p.puerto for p in prefectura.parse(fixture_text("pna_alturas_16nov.html"), AHORA)]

    assert nombres.index("Santa Fe") < nombres.index("Rosario") < nombres.index("San Fernando")


@pytest.mark.parametrize(("altura", "nivel"), [("5.70", "evacuacion"), ("5.30", "alerta"), ("5.29", "normal")])
def test_nivel_se_compara_con_los_umbrales_de_prefectura(altura, nivel):
    (p,) = prefectura.parse(_fila(altura=altura), AHORA)
    assert p.nivel == nivel


@pytest.mark.parametrize(("var", "tendencia"), [("0.10", "sube"), ("-0.05", "baja"), ("0.00", "estable"), ("-", "sin_dato")])
def test_tendencia(var, tendencia):
    (p,) = prefectura.parse(_fila(var=var), AHORA)
    assert p.tendencia == tendencia


@pytest.mark.parametrize("cambio", [
    {"altura": "S/E"}, {"altura": "99.9"}, {"evac": "-"}, {"alerta": ""},
    {"fecha": "sin fecha"}, {"fecha": "16/XYZ/26 - 1000"}, {"rio": "URUGUAY"},
])
def test_filas_rotas_o_ajenas_se_ignoran(cambio):
    assert prefectura.parse(_fila(**cambio), AHORA) == []


def test_lectura_vieja_se_marca_y_no_cuenta_en_el_resumen():
    viejo = prefectura.parse(_fila(fecha="10/NOV/26 - 1000"), AHORA)
    nuevo = prefectura.parse(_fila(puerto="PARANA", fecha="16/NOV/26 - 0800"), AHORA)

    assert viejo[0].viejo is True
    r = prefectura.resumen(viejo + nuevo, AHORA)
    assert r["evacuacion"] == ["Paraná"]
    assert len(r["puertos"]) == 2
    assert r["version"] == prefectura.VERSION


def test_parse_fecha_hora_argentina():
    assert prefectura.parse_fecha("03/NOV/26 - 1200") == datetime(2026, 11, 3, 15, 0, tzinfo=timezone.utc)


def test_html_vacio_o_basura():
    assert prefectura.parse("", AHORA) == []
    assert prefectura.parse("<tr><td>sin etiquetas</td></tr><<<", AHORA) == []
