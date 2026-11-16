#!/bin/bash
S="$1"; FF="$2"; P="$HOME/snap/chromium/common/reel-perfil"
"$FF" -loglevel error -y -f x11grab -draw_mouse 0 -framerate 30 -video_size 540x960 -i :1+66,69 -t 38 -c:v libx264 -preset ultrafast -crf 16 -pix_fmt yuv420p "$S/toma.mp4" &
FFP=$!; sleep 0.5
setsid chromium --user-data-dir="$P" --no-first-run --no-default-browser-check --force-device-scale-factor=1.5 --window-position=40,20 --window-size=360,640 --app=http://127.0.0.1:8791/ >/dev/null 2>&1 &
wait $FFP; echo "ffmpeg $?"
