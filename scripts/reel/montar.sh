#!/bin/bash
# Arma el reel final a partir de la toma cruda y la locución.
#   montar.sh <toma.mp4> <locucion.mp3> <salida.mp4> <ffmpeg>
# - Recorta desde 0,35 s después del fin de la pantalla negra del reel y congela ese cuadro 0,35 s
#   (así no arranca en negro y el audio queda sincronizado).
# - Escala a 1080×1920 y suma el audio. Dura lo que la locución + 0,8 s de placa final.
# - Falla si quedó algún cuadro negro.
set -euo pipefail
export LC_ALL=C  # decimales con punto (awk en castellano usa coma)
TOMA="$1"; AUDIO="$2"; SALIDA="$3"; FF="$4"
CORTE=0.35

# La pantalla negra del reel dura 4 s: se toma el final del último tramo negro de 2,5 s o más
# (en el servidor, antes de que abra el navegador, la pantalla virtual también está en negro).
FIN_NEGRO=$("$FF" -hide_banner -i "$TOMA" -vf blackdetect=d=2.5:pix_th=0.05 -an -f null - 2>&1 \
  | { grep -o "black_end:[0-9.]*" || true; } | tail -1 | cut -d: -f2)
if [ -z "$FIN_NEGRO" ]; then echo "no encontré el negro inicial en $TOMA" >&2; exit 1; fi
LARGO_TOMA=$({ "$FF" -hide_banner -i "$TOMA" 2>&1 || true; } | grep -o "Duration: [0-9:.]*" | cut -d' ' -f2 \
  | awk -F: '{ print $1*3600 + $2*60 + $3 }')
DURACION=$({ "$FF" -hide_banner -i "$AUDIO" 2>&1 || true; } | grep -o "Duration: [0-9:.]*" | cut -d' ' -f2 \
  | awk -F: '{ print $1*3600 + $2*60 + $3 + 0.8 }')
DESDE=$(awk -v a="$FIN_NEGRO" -v c="$CORTE" 'BEGIN { print a + c }')
# si después del negro no queda toma para toda la locución, la página no cargó
if awk -v d="$DESDE" -v l="$LARGO_TOMA" -v n="$DURACION" 'BEGIN { exit !(d + n > l) }'; then
  echo "la toma ($LARGO_TOMA s) queda en negro hasta $FIN_NEGRO s: no alcanza para $DURACION s de reel" >&2; exit 1
fi

"$FF" -loglevel error -y -ss "$DESDE" -i "$TOMA" -i "$AUDIO" -t "$DURACION" -map 0:v -map 1:a \
  -vf "scale=1080:1920:flags=lanczos,fps=30,tpad=start_duration=$CORTE:start_mode=clone" -af apad \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -profile:v high \
  -c:a aac -b:a 160k -movflags +faststart "$SALIDA"

if ! { "$FF" -hide_banner -i "$SALIDA" 2>&1 || true; } | grep -q "Video: h264"; then
  echo "el video final no tiene imagen: $SALIDA" >&2; exit 1
fi
NEGROS=$("$FF" -hide_banner -i "$SALIDA" -vf blackdetect=d=0.05:pix_th=0.1 -an -f null - 2>&1 | grep -c black_start || true)
if [ "$NEGROS" != "0" ]; then echo "quedaron $NEGROS tramos negros en $SALIDA" >&2; exit 1; fi
echo "listo: $SALIDA (${DURACION} s, fin del negro en la toma: ${FIN_NEGRO} s)"
