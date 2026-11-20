from datetime import datetime, timezone

from alertas.fuentes import pronostico_rios as pr

AHORA = datetime(2026, 11, 20, 20, 0, tzinfo=timezone.utc)  # viernes 20, 17 h en Argentina


def test_pronostico_semanal_del_parana(fixture_text):
    puntos = pr.parse_csv(fixture_text("ina_prono_santa_fe.csv"), AHORA)

    assert puntos == [
        {"fecha": "2026-11-24", "medio": 5.84, "inferior": 5.5, "superior": 6.1},
        {"fecha": "2026-12-01", "medio": 5.75, "inferior": 5.5, "superior": 6.1},
    ], "solo los días que vienen: el punto de hoy repite la lectura"


def test_pronostico_diario_del_uruguay(fixture_text):
    puntos = pr.parse_csv(fixture_text("ina_prono_paso_de_los_libres.csv"), AHORA)

    assert puntos[0]["fecha"] == "2026-11-21" and len(puntos) >= 10
    assert all(p["inferior"] <= p["medio"] <= p["superior"] for p in puntos)
    assert puntos[0]["medio"] == 4.91, "redondeado a centímetros"


def test_pronostico_viejo_no_se_muestra(fixture_text):
    dentro_de_un_mes = datetime(2026, 12, 20, tzinfo=timezone.utc)
    assert pr.parse_csv(fixture_text("ina_prono_santa_fe.csv"), dentro_de_un_mes) == []


def test_pronostico_emitido_hace_mucho_no_se_muestra():
    texto = ("timestart,valor,tag,inferior,medio,superior\n"
             "2026-11-01 00:00:00-03:00,5.0,prono,5.0,5.0,5.0\n"
             "2026-11-30 00:00:00-03:00,5.2,prono,5.0,5.2,5.4\n")
    assert pr.parse_csv(texto, AHORA) == [], "una corrida de hace 19 días ya no dice nada"


def test_pronostico_con_columna_main_y_un_mes_de_historia(fixture_text):
    puntos = pr.parse_csv(fixture_text("ina_prono_paso_de_los_libres.csv"), AHORA)
    assert min(p["fecha"] for p in puntos) == "2026-11-21", "lo de antes de hoy no es pronóstico"


def test_csv_con_basura():
    texto = ("timestart,valor,tag,inferior,medio,superior\n"
             "no-es-fecha,1,prono,1,1,1\n"
             "2026-11-20 00:00:00-03:00,5.0,prono,5.0,5.0,5.0\n"
             "2026-11-24 00:00:00-03:00,,prono,,,\n"
             "2026-11-25 00:00:00-03:00,99,prono,98,99,100\n"
             "2026-11-26 00:00:00-03:00,5.1,prono,5.3,5.1,5.4\n"
             "2026-11-27 00:00:00-03:00,5.1,prono,5.0,5.1,5.4\n")
    assert pr.parse_csv(texto, AHORA) == [{"fecha": "2026-11-27", "medio": 5.1, "inferior": 5.0, "superior": 5.4}]
    assert pr.parse_csv("", AHORA) == []


def test_agregar_pone_el_pronostico_en_su_puerto_y_cuenca():
    resumen = {"puertos": [
        {"puerto": "Santa Fe", "cuenca": "Paraná"},
        {"puerto": "San Javier", "cuenca": "Uruguay"},
        {"puerto": "San Javier (Santa Fe)", "cuenca": "Paraná"},
        {"puerto": "Zárate", "cuenca": "Paraná"},
    ]}
    sf = [{"fecha": "2026-11-24", "medio": 5.84, "inferior": 5.5, "superior": 6.1}]
    sj = [{"fecha": "2026-11-21", "medio": 3.6, "inferior": 3.2, "superior": 4.0}]

    nuevo = pr.agregar(resumen, {("Santa Fe", "Paraná"): sf, ("San Javier", "Uruguay"): sj})

    por_nombre = {p["puerto"]: p for p in nuevo["puertos"]}
    assert por_nombre["Santa Fe"]["pronostico"] == sf
    assert por_nombre["San Javier"]["pronostico"] == sj
    assert "pronostico" not in por_nombre["San Javier (Santa Fe)"], "la San Javier del Paraná es otra escala"
    assert "pronostico" not in por_nombre["Zárate"]
    assert "pronostico" not in resumen["puertos"][0], "no modifica el resumen original"
    assert nuevo["pronostico"]["fuente"].startswith("INA")


def test_obtener_sigue_si_un_puerto_falla(monkeypatch, fixture_text):
    def pedir(url):
        if "santa_fe" in url:
            return fixture_text("ina_prono_santa_fe.csv")
        raise TimeoutError("timed out")

    monkeypatch.setattr(pr, "pedir", pedir)
    pronos = pr.obtener(AHORA)

    assert list(pronos) == [("Santa Fe", "Paraná")]
    assert all(url.startswith("https://alerta.ina.gob.ar/") for url in map(pr.url, pr.ARCHIVOS.values()))


def test_pronostico_que_arranca_manana():
    texto = ("timestart,valor,tag,inferior,main,superior\n"
             "2026-11-21 00:00:00-03:00,4.6,prono,4.4,4.6,4.8\n"
             "2026-11-22 00:00:00-03:00,4.7,prono,4.4,4.7,4.9\n")
    assert [p["fecha"] for p in pr.parse_csv(texto, AHORA)] == ["2026-11-21", "2026-11-22"]
