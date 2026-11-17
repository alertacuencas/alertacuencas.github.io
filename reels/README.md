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

Los tiempos de cada paso están en `PASOS`, en [`scripts/reel/reel.js`](../scripts/reel/reel.js).
Si la locución nueva dura distinto, hay que ajustar esos tiempos y, si cambia, la ciudad de ejemplo.

## Cómo se arma cada día

1. Crear `reels/AAAA-MM-DD/` copiando el `guion.md` del día anterior.
2. Bajar los datos del día (`data/parana.json` de la web publicada) y escribir el guion con
   esos números. Elegir la ciudad de ejemplo: conviene la más poblada entre las más graves.
3. Generar la locución con Julieta en ElevenLabs y guardarla como `locucion.mp3` en la carpeta del día.
4. Transcribir el audio con tiempos y pasarlos a la tabla del `guion.md`. Ajustar `PASOS` en `reel.js`.
5. Grabar, recortar y sumar el audio: [`scripts/reel/README.md`](../scripts/reel/README.md).
6. Exportar `reel.mp4` en la carpeta del día, revisarlo y subirlo. Anotar en el `guion.md`
   cuándo se publicó y el texto del posteo.

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
- **Antes de grabar**, cerrar servidores viejos del puerto 8791 (el 17/11 seguía abierto el
  del día anterior, con datos viejos) y no usar la pantalla durante la toma.
- **Lo que cambia cada día** va en `reels/AAAA-MM-DD/reel-dia.js` (ciudad, subtítulos y
  tiempos sacados de la transcripción del audio). `scripts/reel/reel.js` no se toca.
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
