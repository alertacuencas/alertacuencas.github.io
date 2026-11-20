# Reel diario de Instagram (@alertacuencas)

Contexto para armar el video de cada día. Hay una carpeta por día (`reels/AAAA-MM-DD/`) con
su boceto y sus archivos.

## Qué es

- **Formato:** video vertical de 1080×1920, de unos 25 s, para Reels de Instagram.
- **Contenido:** la web (<https://alertacuencas.github.io/>) se recorre sola al ritmo de la
  locución, con subtítulos quemados y una placa final con @alertacuencas.
- **Voz:** ElevenLabs, voz **"Julieta - Argentine Warm & Friendly"**. El 16/11 se usó con
  estabilidad 50 y similitud 75 (`pvc_s50_sim75_v4` en el nombre del archivo).
- **Cómo se escribe el texto para la voz:** texto liso, con **"Etiquetar automáticamente"
  apagado**. Frases cortas, con puntos y comas para las pausas ("Hoy, ocho ciudades…",
  "Otras cuatro, en alerta.", "Defensa Civil, ciento tres."). Los números van en letras.
  Modelo **Eleven v4**.
- **Tono:** de observación, no de alerta. Contamos lo que dicen los datos ("el río pasó por
  7 cm el nivel de evacuación") y nunca emitimos niveles propios. Ver la sección 0 de
  [`docs/diseno-fase1.md`](../docs/diseno-fase1.md).

## Estructura del guion (siempre igual)

| # | Bloque | En pantalla |
|---|---|---|
| 1 | **Hoy:** cuántas ciudades del Paraná están en evacuación o en alerta, y desde dónde hasta dónde | Paso 1 · titular y cartel del Paraná |
| 2 | **Costa y Delta:** cómo está el río en Buenos Aires y el Delta | Cartel de la costa, resaltado |
| 3 | **"¿Y en tu ciudad?"** | Paso 2 · Tu lugar |
| 4 | **Una ciudad de ejemplo** con su dato | Se escribe la ciudad y aparece la ficha |
| 5 | **"Acá está todo el Paraná, de lo más grave a lo más tranquilo."** | Paso 3 · El río |
| 6 | **"No somos un sistema oficial. Ante una emergencia, Defensa Civil 103."** | Aviso "No es un sistema oficial" |
| 7 | **"Seguí a Alerta Cuencas."** | Placa final @alertacuencas |

**Con ciudades del Paraná en evacuación, solo lo crítico** (desde el 18/11):

| # | Bloque | En pantalla |
|---|---|---|
| 1 | **Hoy:** cuántas ciudades están en evacuación (sin rango ni las de alerta) | Paso 1 · titular y cartel del Paraná |
| 2 | **"¿Dónde está más complicado?"** | Paso 2 · Tu lugar |
| 3 | **Las 4 que más pasaron el nivel de evacuación**, con su número; la ficha es la peor | Se escribe la ciudad y aparece la ficha |
| 4 | **El resto de las ciudades en evacuación** y si el río sube, baja o está estable en la mayoría | Paso 3 · El río |
| 5–6 | No somos oficiales · Seguí a Alerta Cuencas | Igual que arriba |

La costa (sudestada, "el río está tranquilo") no entra ni en la voz ni en la portada: no tiene que
ver con el Paraná y desvía la atención. Solo entra si el Delta mismo está en alerta o el SMN tiene
una alerta vigente en el AMBA.

**Todos los ríos en la misma línea, de lo más grave para abajo** (desde el 18/11): el Uruguay, el
Paraguay, el Río de la Plata y los afluentes entran igual que el Paraná. El "hoy" cuenta las ciudades
en evacuación por río ("tres ciudades están en evacuación: una sobre el Uruguay y dos sobre el
Paraná"), las peores se nombran con su río si no es el Paraná ("En San Javier, sobre el Uruguay, …")
y al final se suman, sin nombrar ciudades, los ríos que solo están en alerta ("Además, el Paraguay
está en alerta"). Con ciudades en evacuación no se dice que la costa está tranquila.

Los datos tienen que ser los de Prefectura, que trae todos los puertos (San Javier, Barranqueras,
Victoria) y la lectura del día. El respaldo del INA que usa GitHub no los tiene y puede venir
atrasado: si el guion automático dice otra cantidad de ciudades, prepararlo desde la PC.

Los tiempos de cada paso están en `PASOS`, en [`scripts/reel/reel.js`](../scripts/reel/reel.js).
Si la locución nueva dura distinto, hay que ajustar esos tiempos y, si cambia, la ciudad de ejemplo.

## Cómo se arma cada día (automático, salvo la voz)

1. **09:30, solo** ([`reel-preparar`](../.github/workflows/reel-preparar.yml)): consulta las
   fuentes en el momento (no depende del monitor), arma el guion con
   [`alertas/reel/`](../alertas/reel/), el texto para ElevenLabs, el posteo y la portada, los
   sube a la release `reel-AAAA-MM-DD`, guarda `reels/AAAA-MM-DD/guion.md` y abre un **issue
   "Reel del DD/MM"** con el texto listo para copiar y lo que haya que revisar (por ejemplo,
   si la lectura del Paraná todavía es la de ayer).
2. **Vos, unos 2 minutos:** pegás el texto en ElevenLabs con Julieta (Eleven v4, 50 %, 75 %,
   etiquetado apagado), descargás el mp3 y corrés `scripts/reel/subir-voz.sh` desde el repo.
3. **Solo** ([`reel-armar`](../.github/workflows/reel-armar.yml)): transcribe la voz, calcula
   los tiempos (`reel-dia.js`), graba la web en una pantalla virtual, monta el video sin negro
   y deja `reel.mp4` en la release, con un comentario en el issue para revisarlo.
4. **Publicar:** por ahora a mano desde Chrome (video en 9:16, portada propia, texto del
   posteo y etiqueta de IA). Con el token de la API de Instagram se puede automatizar.

Para rehacer un día (por ejemplo, si llegó la lectura nueva del INA): correr `reel-preparar`
desde Actions → "Run workflow". Si el `guion.md` del día se editó a mano, no se pisa.
El bot hace commits en `main` todos los días: hacé `git pull` antes de trabajar.

Probar en la PC: `uv run python -m alertas.reel preparar --datos web/data --dia /tmp/prueba`.

## Reglas aprendidas (no repetir errores)

- **Nada de arranque en negro.** La grabación tiene unos 4 s de negro más un fundido. Se
  recorta desde unos 0,35 s después del fin del negro (`blackdetect`) y ese primer cuadro
  nítido se congela con `tpad=start_duration=0.35:start_mode=clone`, así el audio queda
  sincronizado. Antes de publicar se verifica que `blackdetect` no encuentre nada.
- **Portada propia** (`portada.png`, 1080×1920). Si no se elige una, Instagram usa el
  primer cuadro: el 16/11 la grilla del perfil mostraba el reel en negro. La portada es la
  del carrusel sin el "1/3" y con el contenido importante en el centro, porque la grilla recorta.
  Al publicar se sube en "Portada → Seleccionar de la computadora".
- **Solo lo que siga vigente.** No mencionar en la voz, la portada ni el posteo alertas del
  SMN ya vencidas (el 17/11 la web todavía mostraba una alerta amarilla vencida a las 8:59).
- **El link no es clickeable** ni en el reel ni en el texto del posteo. La dirección
  `alertacuencas.github.io` va escrita en la placa final y en el texto, con "(link en el perfil)".
- **Texto para la voz:** liso, con "Etiquetar automáticamente" apagado (ver arriba).
- **Voz corta (desde el 21/11):** el plan gratis de ElevenLabs da 10.000 créditos por mes (1 por letra), o sea
  unas 280 letras por día. La voz nombra solo la ciudad más complicada; las demás, la tendencia y el detalle
  van en pantalla y en el posteo. Generar la voz una sola vez por día: si hay que rehacer el guion, antes.
- **Antes de grabar**, cerrar servidores viejos del puerto 8791 (el 17/11 seguía abierto el
  del día anterior, con datos viejos) y no usar la pantalla durante la toma.
- **Lo que cambia cada día** va en `reels/AAAA-MM-DD/reel-dia.js` (ciudad, subtítulos y
  tiempos sacados de la transcripción del audio). `scripts/reel/reel.js` no se toca.
- **Subtítulos y franja en la zona segura:** Instagram tapa unos 400 px abajo y 220 px
  arriba. Los subtítulos van a 405 px del borde de abajo y la franja con la dirección,
  debajo del encabezado de la web.
- **El guion lo arma el código** ([`alertas/reel/guion.py`](../alertas/reel/guion.py)): la
  ciudad de ejemplo es la que más pasó el nivel de evacuación (o la más cerca, si no hay
  ninguna), y las alertas del SMN vencidas no se mencionan.
- **Publicar con la etiqueta de IA**, porque la voz es de ElevenLabs.

## Qué va en git

- **Sí:** cada `guion.md` y `reel-dia.js`, con el boceto, los tiempos, el texto del posteo y las notas.
- **No** (está en `.gitignore`): videos, audio, imágenes y la carpeta `trabajo/` (toma cruda, copia
  del sitio, cuadros). Un video pesa unos 7 MB y el repo es público.

## Checklist antes de publicar

- [ ] Los números del guion coinciden con `parana.json` del día.
- [ ] La ciudad de ejemplo dice lo mismo en la ficha y en la voz.
- [ ] Los subtítulos están bien sincronizados y no los tapa la interfaz de Instagram.
- [ ] Aparece el aviso "No es un sistema oficial" y el 103.
- [ ] Video de 1080×1920 con audio.
