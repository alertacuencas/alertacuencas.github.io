#!/bin/bash
# Reel diario, paso 1 desde la PC (cron de las 07:00). Prefectura responde desde acá y no desde
# GitHub: así el guion sale con todos los puertos y la lectura del día. Consulta las fuentes, arma
# guion, texto para la voz, posteo y portada, los sube a la release reel-AAAA-MM-DD, guarda el
# guion en el repo y avisa con el issue del día. Si la voz de hoy ya está subida, no hace nada.
#   scripts/reel/preparar-local.sh [--rehacer]
set -euo pipefail
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
REPO=alertacuencas/alertacuencas.github.io
RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$RAIZ"
FECHA=$(TZ=America/Argentina/Buenos_Aires date +%F)
DIA="reels/$FECHA"
TAG="reel-$FECHA"
echo "== $(date -Is) preparando $TAG"

if [ "${1:-}" != "--rehacer" ] && gh release view "$TAG" --repo "$REPO" --json assets --jq '.assets[].name' 2>/dev/null | grep -qx locucion.mp3; then
  echo "la voz de hoy ya está subida: no rehago el guion para no desfasarlo del audio"; exit 0
fi

git pull -q --rebase --autostash
uv run --no-dev python -m alertas.cli poll
VIA=$(jq -r '.via' web/data/parana.json)
echo "Paraná vía: $VIA"
uv run --no-dev python -m alertas.reel preparar --datos web/data --dia "$DIA"
cp web/data/parana.json web/data/estado.json web/data/serie.json "$DIA/"

gh release view "$TAG" --repo "$REPO" >/dev/null 2>&1 || \
  gh release create "$TAG" --repo "$REPO" --prerelease --title "Reel $FECHA" \
    --notes "Material del reel diario. Ver reels/$FECHA/guion.md."
gh release upload "$TAG" --repo "$REPO" --clobber "$DIA"/guion.md "$DIA"/guion.json "$DIA"/texto-voz.txt \
  "$DIA"/posteo.txt "$DIA"/portada.png "$DIA"/ahora.txt "$DIA"/parana.json "$DIA"/estado.json "$DIA"/serie.json

git add "$DIA/guion.md"
if git commit -q -m "docs: guion del reel del $FECHA"; then
  git pull -q --rebase --autostash && git push -q
fi
scripts/reel/avisar-issue.sh "$DIA" "$FECHA" "$REPO"
echo "listo: $TAG (Paraná vía $VIA)"
