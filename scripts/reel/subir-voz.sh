#!/bin/bash
# Sube la locución de hoy y arranca el armado del reel en GitHub Actions.
#   scripts/reel/subir-voz.sh [archivo.mp3]
# Sin argumento toma el mp3 de ElevenLabs más nuevo de ~/Descargas.
set -euo pipefail
REPO=alertacuencas/alertacuencas.github.io
RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
FECHA=$(TZ=America/Argentina/Buenos_Aires date +%F)
DIA="$RAIZ/reels/$FECHA"

MP3="${1:-$(ls -t "$HOME"/Descargas/ElevenLabs_*.mp3 2>/dev/null | head -1 || true)}"
if [ -z "$MP3" ] || [ ! -f "$MP3" ]; then echo "no encontré el mp3 de ElevenLabs en ~/Descargas" >&2; exit 1; fi
echo "locución: $MP3"
case "$(basename "$MP3")" in
  *"$FECHA"*) ;;
  *) read -r -p "El archivo no es de hoy ($FECHA). ¿Lo uso igual? [s/N] " r; [ "$r" = "s" ] || exit 1 ;;
esac

if ! gh release view "reel-$FECHA" --repo "$REPO" >/dev/null 2>&1; then
  echo "todavía no está preparado el reel de hoy (falta la release reel-$FECHA); corré el workflow reel-preparar" >&2
  exit 1
fi

mkdir -p "$DIA"
cp "$MP3" "$DIA/locucion.mp3"
gh release upload "reel-$FECHA" "$DIA/locucion.mp3" --repo "$REPO" --clobber
gh workflow run reel-armar.yml --repo "$REPO" -f fecha="$FECHA"
echo "listo: se está armando el reel del $FECHA. Seguilo con: gh run watch --repo $REPO"
