#!/bin/bash
# Crea o actualiza el issue "Reel del DD/MM" con el texto para ElevenLabs, los avisos y el posteo.
#   scripts/reel/avisar-issue.sh <carpeta del día> <AAAA-MM-DD> <dueño/repo>
set -euo pipefail
D="$1"; F="$2"; REPO="$3"
CUERPO=$(mktemp)
trap 'rm -f "$CUERPO"' EXIT
{
  echo "## 1. Texto para ElevenLabs"
  echo
  echo "Julieta - Argentine Warm & Friendly · **Eleven v4** · estabilidad **50 %** · similitud **75 %** · \"Etiquetar automáticamente\" **apagado**."
  echo
  echo '```'
  cat "$D/texto-voz.txt"
  echo '```'
  echo
  echo "## 2. Subir la voz"
  echo
  echo 'Descargá el mp3 y corré `scripts/reel/subir-voz.sh` desde el repo.'
  echo
  echo "## Para revisar"
  echo
  jq -r 'if (.avisos | length) == 0 then "- Sin avisos." else (.avisos[] | "- ⚠️ " + .) end' "$D/guion.json"
  echo
  echo "## Texto del posteo"
  echo
  sed 's/^/> /' "$D/posteo.txt"
  echo
  echo "Portada y datos: release [reel-$F](https://github.com/$REPO/releases/tag/reel-$F)."
} > "$CUERPO"
gh label create reel --repo "$REPO" --color 7fd3ff --description "Reel diario de Instagram" --force >/dev/null
TITULO="Reel del $(date -d "$F" +%d/%m)"
N=$(gh issue list --repo "$REPO" --label reel --state open --search "in:title \"$TITULO\"" --json number --jq '.[0].number // empty')
if [ -n "$N" ]; then gh issue edit "$N" --repo "$REPO" --body-file "$CUERPO" >/dev/null; else gh issue create --repo "$REPO" --title "$TITULO" --label reel --body-file "$CUERPO"; fi
