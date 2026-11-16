# Reel del estado diario

Video vertical (1080×1920, ~25 s): la web recorrida sola al ritmo de una locución de
ElevenLabs (voz "Julieta - Argentine Warm & Friendly"), con subtítulos quemados.

## Guion del 16/11/2026 (recuperado del audio; tiempos en segundos)

| Tiempo | Texto | En pantalla |
|---|---|---|
| 0,0 | Hoy ocho ciudades del Paraná están en evacuación, desde Goya hasta Diamante, otras cuatro en alerta. | Paso 1 · Hoy: titular y cartel del Paraná |
| 6,6 | En Buenos Aires y el Delta, el río está tranquilo. | Cartel de la costa, resaltado |
| 9,5 | ¿Y en tu ciudad? | Paso 2 · Tu lugar |
| 10,5 | En Santa Fe, el río pasó por 7 centímetros el nivel de evacuación. | Se escribe "Santa Fe" y aparece la ficha |
| 14,2 | Acá está todo el Paraná, de lo más grave a lo más tranquilo. | Paso 3 · El río: lista por gravedad |
| 17,8 | No somos un sistema oficial. Ante una emergencia, Defensa Civil 103. | Aviso "No es un sistema oficial", resaltado |
| 22,6 | Seguí a Alerta Cuencas. | Placa final @alertacuencas |

Antes de grabar, verificar que los números del guion coincidan con `data/parana.json` del día.

## Cómo se graba (X11, sin navegador oculto)

1. Copiar `web/` a una carpeta temporal, bajar `data/*.json` de la web publicada y agregar
   `<script src="reel.js"></script>` después de `app.js` en el `index.html` de la copia.
2. Servirla en `127.0.0.1:8791` (`python3 -m http.server`).
3. `grabar.sh <carpeta> <ffmpeg>`: abre Chromium en modo app a 540×960 (escala 1,5) y graba esa
   zona con `x11grab` 38 s. La página espera 4 s en negro y arranca el recorrido. Si la
   ventana no queda en `+66,69`, ajustar con `xwininfo -root -tree`.
4. Buscar el fin del negro (`blackdetect`), recortar desde ahí, escalar a 1080×1920 y sumar el audio.

ffmpeg sin instalar nada: `uv run --with imageio-ffmpeg python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"`.
