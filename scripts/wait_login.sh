#!/usr/bin/env bash
# wait_login.sh — 开一个带调试端口的 Edge，等用户在里面登录阿里国际站
#
# ⚠️ 浏览器必须在**同一次 bash 调用**里启动并访问：本环境的 bash 每次调用
#    结束后会回收子进程/端口，跨调用连不上 127.0.0.1:9333。
#    所以「启动 + 等登录」必须在一条命令里跑完。
#
# 用法：bash scripts/wait_login.sh [最长等待秒数，默认 400]
set -u

EDGE="/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
NODE="C:/Users/Administrator/.workbuddy/binaries/node/versions/22.22.2-6/node.exe"
PROFILE="C:/Users/Administrator/AppData/Local/Temp/aqcedge3"
PROBE_URL="https://www.alibaba.com/product-detail/_1601799709236.html"
MAXWAIT="${1:-400}"

cd "C:/Users/Administrator/.qclaw/workspace/aquaclean-home" || exit 1

# 这个 profile 还活着的话，新实例会退化成「开个标签」而拿不到调试端口
if curl -s --noproxy '*' --max-time 3 "http://127.0.0.1:9333/json/version" >/dev/null 2>&1; then
  echo "端口 9333 已被占用，复用现有实例"
else
  "$EDGE" --remote-debugging-port=9333 --user-data-dir="$PROFILE" \
    --no-first-run --no-default-browser-check --disable-component-update \
    "https://login.alibaba.com/" >/tmp/aqc_edge.log 2>&1 &
  echo "已启动 Edge (PID $!)，窗口里请登录阿里国际站"
fi

sleep 8

DEADLINE=$(( $(date +%s) + MAXWAIT ))
while true; do
  OUT=$("$NODE" scripts/probe_login.js "$PROBE_URL" 2>/dev/null | tail -1)
  echo "$(date +%H:%M:%S) $OUT"
  case "$OUT" in
    \[OK\]*) echo ">>> 登录态已就绪"; break ;;
    NOPORT)  echo ">>> 调试端口没了，浏览器已退出"; exit 2 ;;
  esac
  if [ "$(date +%s)" -ge "$DEADLINE" ]; then
    echo ">>> 等待超时（${MAXWAIT}s），仍未登录"
    exit 3
  fi
  sleep 4
done
