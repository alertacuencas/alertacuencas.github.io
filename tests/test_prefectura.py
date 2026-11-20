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
    assert (santa_fe.lat, santa_fe.lon) == (-31.6515, -60.7002)
    assert puertos["Rosario"].lat is not None
    assert "Zárate" in puertos
    assert "Paso de la Patria" in puertos


def test_todos_los_puertos_tienen_ubicacion_en_el_mapa_salvo_los_pendientes(fixture_text):
    sin_ubicacion = {prefectura._sin_tildes(p.puerto.upper())
                     for p in prefectura.parse(fixture_text("pna_alturas_16nov.html"), AHORA) if p.lat is None}
    assert sin_ubicacion <= prefectura.SIN_UBICACION


def test_trae_todos_los_rios_con_su_cuenca_y_deja_afuera_las_represas(fixture_text):
    puertos = {p.puerto: p for p in prefectura.parse(fixture_text("pna_alturas_16nov.html"), AHORA)}

    assert {p.rio for p in puertos.values()} <= prefectura.RIOS
    assert all(p.altura < 30 for p in puertos.values()), "las represas (150 m, 35 m) no entran"
    assert puertos["Concordia"].cuenca == "Uruguay"
    assert puertos["Isla del Cerrito"].cuenca == "Paraguay"
    assert puertos["Buenos Aires"].cuenca == "Río de la Plata"
    assert puertos["San Fernando"].cuenca == "Paraná", "el Delta cuenta como Paraná"
    assert puertos["San Javier"].cuenca == "Uruguay" and puertos["San Javier (Santa Fe)"].cuenca == "Paraná"


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
    {"fecha": "sin fecha"}, {"fecha": "16/XYZ/26 - 1000"}, {"rio": "EMBALSE RIO HONDO"},
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


# ── Respaldo vía INA (Prefectura no responde desde GitHub Actions) ──

def test_series_ina_un_puerto_por_nombre_de_norte_a_sur(fixture_text):
    series = prefectura.parse_series_ina(fixture_text("ina_series_alturas_prefe.json"))
    nombres = [s.puerto for s in series]

    assert len(nombres) == len(set(nombres)), "el INA repite puertos en series sin datos"
    assert nombres.index("Corrientes") < nombres.index("Santa Fe") < nombres.index("Rosario") < nombres.index("Zárate")
    assert nombres.index("Santa Ana") < nombres.index("Posadas") < nombres.index("Itatí"), "orden del río, no latitud"
    santa_fe = next(s for s in series if s.puerto == "Santa Fe")
    assert (santa_fe.id, santa_fe.alerta, santa_fe.evacuacion) == (30, 5.3, 5.7)
    assert {s.rio for s in series} <= prefectura.RIOS_INA


def test_series_ina_traen_los_otros_rios_con_la_cuenca_de_prefectura(fixture_text):
    series = {s.puerto: s for s in prefectura.parse_series_ina(fixture_text("ina_series_alturas_prefe.json"))}

    assert series["Concordia"].cuenca == "Uruguay"
    assert series["Paso de los Libres"].cuenca == "Uruguay"
    assert series["Paranacito"].cuenca == "Uruguay", "Villa Paranacito, con el nombre de Prefectura"
    assert series["Formosa"].cuenca == "Paraguay" and series["Pilcomayo"].cuenca == "Paraguay"
    assert series["Andresito"].cuenca == "Iguazú"
    assert series["Puerto Ruiz"].cuenca == "Gualeguay"
    assert series["Gualeguaychú"].cuenca == series["Boca Gualeguaychú"].cuenca == "Gualeguaychú"
    assert series["Buenos Aires"].cuenca == "Río de la Plata"
    assert series["Santa Fe"].cuenca == series["Tigre"].cuenca == "Paraná"
    assert "Pepirí Miní" not in series, "sin niveles de alerta no hay con qué comparar"
    nombres = list(series)
    assert nombres.index("Santo Tomé") < nombres.index("Concordia") < nombres.index("Colón"), "de norte a sur"


def test_tigre_y_el_delta_cuentan_como_delta_tambien_via_ina(fixture_text):
    from alertas.publicar import resumen
    series = {s.puerto: s for s in prefectura.parse_series_ina(fixture_text("ina_series_alturas_prefe.json"))}
    for puerto in ("Tigre", "San Fernando", "Chaná Miní", "Canal Nuevo", "Baradero"):
        assert series[puerto].rio in resumen.RIOS_DELTA, puerto


def test_puerto_ina_lleva_la_cuenca(fixture_text):
    serie = next(s for s in prefectura.parse_series_ina(fixture_text("ina_series_alturas_prefe.json"))
                 if s.puerto == "Concordia")
    p = prefectura.puerto_ina(serie, [(AHORA, 9.0)], AHORA)
    assert p.cuenca == "Uruguay"


def test_puerto_ina_desde_observaciones_reales(fixture_text):
    serie = next(s for s in prefectura.parse_series_ina(fixture_text("ina_series_alturas_prefe.json"))
                 if s.puerto == "Santa Fe")
    obs = prefectura.parse_obs_ina(fixture_text("ina_obs_santa_fe.json"))

    p = prefectura.puerto_ina(serie, obs, AHORA)

    assert (p.altura, p.variacion, p.tendencia, p.nivel) == (5.77, 0.0, "estable", "evacuacion")
    assert p.ts == "2026-11-16T03:00:00Z"
    assert round(p.lat, 2) == -31.65 and round(p.lon, 2) == -60.70
    assert p.viejo is False


def test_puerto_ina_sin_observaciones_o_con_basura():
    serie = prefectura.SerieIna(1, "X", "PARANAINF", -31.0, -60.0, 5.0, 5.5, "Paraná")
    assert prefectura.puerto_ina(serie, [], AHORA) is None
    basura = '[{"timestart": "no-es-fecha", "valor": 1}, {"timestart": "2026-11-16T03:00:00Z", "valor": null},' \
             ' {"timestart": "2026-11-16T03:00:00Z", "valor": 999}]'
    assert prefectura.parse_obs_ina(basura) == []


def test_series_ina_ignora_filas_incompletas():
    texto = '{"rows": [{"id": 1, "estacion": {"rio": "PARANAINF", "nivel_alerta": null}}, {"id": 2}]}'
    assert prefectura.parse_series_ina(texto) == []


def test_respaldo_usa_el_ina_si_prefectura_no_responde(monkeypatch, fixture_text):
    def caida(ahora):
        raise TimeoutError("timed out")

    respuestas = {prefectura.INA_SERIES: fixture_text("ina_series_alturas_prefe.json")}
    monkeypatch.setattr(prefectura, "obtener", caida)
    monkeypatch.setattr(prefectura, "pedir",
                        lambda url: respuestas.get(url) or fixture_text("ina_obs_santa_fe.json"))

    puertos, via = prefectura.obtener_con_respaldo(AHORA)

    assert via == "ina"
    assert "Santa Fe" in {p.puerto for p in puertos}
    r = prefectura.resumen(puertos, AHORA, via)
    assert r["via"] == "ina" and "INA" in r["fuente"]


def test_respaldo_prefiere_prefectura(monkeypatch, fixture_text):
    monkeypatch.setattr(prefectura, "obtener", lambda a: prefectura.parse(fixture_text("pna_alturas_16nov.html"), a))
    puertos, via = prefectura.obtener_con_respaldo(AHORA)
    assert via == "prefectura" and puertos


def test_ina_sin_alturas_es_un_error(monkeypatch):
    monkeypatch.setattr(prefectura, "pedir", lambda url: '{"rows": []}')
    with pytest.raises(RuntimeError):
        prefectura.obtener_ina(AHORA)


def test_ina_un_puerto_caido_no_frena_a_los_demas(monkeypatch, fixture_text):
    def pedir(url):
        if url == prefectura.INA_SERIES:
            return fixture_text("ina_series_alturas_prefe.json")
        if "/series/30/" in url:
            raise TimeoutError("Santa Fe no responde")
        return fixture_text("ina_obs_santa_fe.json")

    monkeypatch.setattr(prefectura, "pedir", pedir)
    nombres = {p.puerto for p in prefectura.obtener_ina(AHORA)}
    assert "Santa Fe" not in nombres and "Rosario" in nombres
