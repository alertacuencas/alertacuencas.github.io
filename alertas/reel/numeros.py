"""Números y distancias para la voz (en letras) y para los subtítulos (con cifras)."""

UNIDADES = ["cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve",
            "diez", "once", "doce", "trece", "catorce", "quince", "dieciséis", "diecisiete", "dieciocho",
            "diecinueve", "veinte", "veintiuno", "veintidós", "veintitrés", "veinticuatro", "veinticinco",
            "veintiséis", "veintisiete", "veintiocho", "veintinueve"]
DECENAS = {30: "treinta", 40: "cuarenta", 50: "cincuenta", 60: "sesenta", 70: "setenta", 80: "ochenta", 90: "noventa"}
CENTENAS = {1: "ciento", 2: "doscientos", 3: "trescientos", 4: "cuatrocientos", 5: "quinientos",
            6: "seiscientos", 7: "setecientos", 8: "ochocientos", 9: "novecientos"}


def _menor_cien(n: int) -> str:
    if n < 30:
        return UNIDADES[n]
    decena, unidad = divmod(n, 10)
    return DECENAS[decena * 10] + (f" y {UNIDADES[unidad]}" if unidad else "")


def en_letras(n: int, femenino: bool = False, apocope: bool = False) -> str:
    """De 0 a 999. `femenino` para contar ciudades ("una", "veintiuna"); `apocope` delante
    de un sustantivo masculino ("un centímetro", "veintiún metros", "treinta y un")."""
    if not 0 <= n <= 999:
        raise ValueError(f"fuera de rango: {n}")
    if n == 100:
        texto = "cien"
    elif n < 100:
        texto = _menor_cien(n)
    else:
        centena, resto = divmod(n, 100)
        texto = CENTENAS[centena] + (f" {_menor_cien(resto)}" if resto else "")
    if femenino and texto.endswith("uno"):
        texto = texto[:-3] + "una"
    elif apocope and texto.endswith("veintiuno"):
        texto = texto[:-9] + "veintiún"
    elif apocope and texto.endswith("uno"):
        texto = texto[:-3] + "un"
    return texto


def distancia_voz(metros: float) -> str:
    cm = round(abs(metros) * 100)
    if cm < 100:
        return f"{en_letras(cm, apocope=True)} centímetro{'' if cm == 1 else 's'}"
    m, resto = divmod(cm, 100)
    texto = "un metro" if m == 1 else f"{en_letras(m, apocope=True)} metros"
    return texto + (f" con {en_letras(resto, apocope=True)} centímetro{'' if resto == 1 else 's'}" if resto else "")


def distancia_sub(metros: float) -> str:
    cm = round(abs(metros) * 100)
    if cm < 100:
        return f"{cm} cm"
    if cm % 100 == 0:
        return f"{cm // 100} m"
    return f"{cm / 100:.2f}".replace(".", ",") + " m"
