#!/bin/bash
# Graba el recorrido de la web en un servidor sin pantalla (GitHub Actions), con una
# pantalla virtual (Xvfb) del tamaño del reel. Es la misma técnica que grabar.sh, pero
# sin depender del escritorio de nadie.
#   grabar-ci.sh <carpeta-del-día> <carpeta-con-los-json> <ffmpeg> <toma.mp4>
set -euo pipefail
export LC_ALL=C  # decimales con punto (awk en castellano usa coma)
DIA="$1"; DATOS="$2"; FF="$3"; TOMA="$4"
RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
SITIO="$(mktemp -d)"
PANTALLA=:99

# 1. Copia de la web con los datos del día y el recorrido
cp "$RAIZ"/web/*.js "$RAIZ"/web/*.css "$RAIZ"/web/index.html "$SITIO"/
mkdir -p "$SITIO/data"
cp "$DATOS"/*.json "$SITIO/data/"
cp "$RAIZ/web/data/zonas.geojson" "$SITIO/data/" 2>/dev/null || true
cp "$RAIZ/scripts/reel/reel.js" "$DIA/reel-dia.js" "$SITIO"/
sed -i 's|\(<script src="app.js"[^>]*></script>\)|\1\n  <script src="reel-dia.js"></script>\n  <script src="reel.js"></script>|' "$SITIO/index.html"
grep -q 'reel-dia.js' "$SITIO/index.html" || { echo "no pude insertar el recorrido en index.html" >&2; exit 1; }

# 2. Servidor local, pantalla virtual de 1080×1920 y navegador a 360×640 con escala 3
python3 -m http.server 8791 --bind 127.0.0.1 --directory "$SITIO" >/dev/null 2>&1 &
SERVIDOR=$!
Xvfb "$PANTALLA" -screen 0 1080x1920x24 -nolisten tcp >/dev/null 2>&1 &
XVFB=$!
trap 'kill $SERVIDOR $XVFB 2>/dev/null || true; rm -rf "$SITIO"' EXIT
sleep 2

DURACION=$({ "$FF" -hide_banner -i "$DIA/locucion.mp3" 2>&1 || true; } | grep -o "Duration: [0-9:.]*" | cut -d' ' -f2 \
  | awk -F: '{ printf "%d", $1*3600 + $2*60 + $3 + 14 }')  # 4 s de negro + carga + placa final

"$FF" -loglevel error -y -f x11grab -draw_mouse 0 -framerate 30 -video_size 1080x1920 -i "$PANTALLA+0,0" \
  -t "$DURACION" -c:v libx264 -preset ultrafast -crf 16 -pix_fmt yuv420p "$TOMA" &
GRABACION=$!
sleep 0.5
DISPLAY="$PANTALLA" google-chrome --user-data-dir="$(mktemp -d)" --no-first-run --no-default-browser-check \
  --disable-gpu --hide-scrollbars --force-device-scale-factor=3 --window-position=0,0 --window-size=360,640 \
  --autoplay-policy=no-user-gesture-required --app=http://127.0.0.1:8791/ >/dev/null 2>&1 &
NAVEGADOR=$!
wait $GRABACION
kill $NAVEGADOR 2>/dev/null || true
echo "toma: $TOMA ($DURACION s)"
