#!/bin/bash
# 云端开发、Mac 真机看效果。
#   tools/mac.sh sync                       把源码同步到 Mac 的 ~/avdetect 并构建
#   tools/mac.sh shot <名字> <文件|-> [延迟毫秒] [页面脚本]   在 Mac 上启动、截窗口图，拉回 /tmp/avd-mac/<名字>.png
# Mac 上的 Node / ffmpeg 在 ~/local/node/bin；Electron 复用律衡构建目录里下好的那份（node_modules/electron/dist 是软链）
set -e
ROOT=$(cd "$(dirname "$0")/.." && pwd)
case "$1" in
  sync)
    cd "$ROOT"
    tar czf - --exclude=node_modules --exclude=out --exclude=__pycache__ --exclude=.git . | ssh local 'mkdir -p ~/avdetect && cd ~/avdetect && tar xzf -'
    ssh local 'export PATH=$HOME/local/node/bin:$PATH && cd ~/avdetect/desktop && npx electron-vite build 2>&1 | grep -E "rror|built in" | tail -3'
    ;;
  shot)
    NAME=$2; FILE=$3; DELAY=${4:-5000}; JS=${5:-}
    mkdir -p /tmp/avd-mac
    ARG=""; [ "$FILE" != "-" ] && ARG="$FILE"
    ssh local "export PATH=\$HOME/local/node/bin:\$PATH; rm -f /tmp/avd-$NAME.png; cd ~/avdetect/desktop && \
      AVD_SNAPSHOT=/tmp/avd-$NAME.png AVD_SNAPSHOT_DELAY=$DELAY AVD_SNAPSHOT_JS=$(printf %q "$JS") \
      perl -e \"alarm shift; exec @ARGV\" 60 node_modules/electron/dist/Electron.app/Contents/MacOS/Electron . $ARG >/tmp/avd-$NAME.log 2>&1; ls -la /tmp/avd-$NAME.png"
    scp -q local:/tmp/avd-$NAME.png /tmp/avd-mac/$NAME.png && echo "/tmp/avd-mac/$NAME.png"
    ;;
esac
