# Reel del estado diario

Video vertical (1080×1920, ~25 s): la web recorrida sola al ritmo de una locución de
ElevenLabs (voz "Julieta - Argentine Warm & Friendly"), con subtítulos quemados.

El guion de cada día, el contexto y el checklist están en [`reels/`](../../reels/README.md).
Antes de grabar, verificar que los números del guion coincidan con `data/parana.json` del día.

## Cómo se graba (X11, sin navegador oculto)

1. Copiar `web/` a una carpeta temporal, bajar `data/*.json` de la web publicada y agregar
   `<script src="reel-dia.js"></script><script src="reel.js"></script>` después de `app.js`
   (copiando `reel-dia.js` desde `reels/AAAA-MM-DD/`) en el `index.html` de la copia.
2. Servirla en `127.0.0.1:8791` (`python3 -m http.server`).
3. `grabar.sh <carpeta> <ffmpeg>`: abre Chromium en modo app a 540×960 (escala 1,5) y graba esa
   zona con `x11grab` 38 s. La página espera 4 s en negro y arranca el recorrido. Si la
   ventana no queda en `+66,69`, ajustar con `xwininfo -root -tree`.
4. Buscar el fin del negro (`blackdetect`), recortar desde 0,35 s después y congelar ese cuadro con
   `tpad=start_duration=0.35:start_mode=clone` (así no arranca en negro), escalar a 1080×1920 y sumar el audio.

ffmpeg sin instalar nada: `uv run --with imageio-ffmpeg python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"`.
