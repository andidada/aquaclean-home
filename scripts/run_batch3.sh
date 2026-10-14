#!/usr/bin/env bash
# run_batch3.sh — 一条命令内完成：开浏览器 → 等登录 → 采集 → 补属性 → 关浏览器
#
# ⚠️ 本环境 bash 每次调用结束会回收子进程与 localhost 端口，
#    跨调用连不上 127.0.0.1:9333，所以必须全程在**同一次调用**里跑完。
#
# 用法：bash scripts/run_batch3.sh [最长等登录秒数，默认 240]
set -u

EDGE="/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
NODE="C:/Users/Administrator/.workbuddy/binaries/node/versions/22.22.2-6/node.exe"
PROFILE="C:/Users/Administrator/AppData/Local/Temp/aqcedge3"
LINKS="scraped/product_urls_batch3.txt"
PROBE_URL="https://www.alibaba.com/product-detail/_1601799709236.html"
MAXWAIT="${1:-240}"

cd "C:/Users/Administrator/.qclaw/workspace/aquaclean-home" || exit 1

"$EDGE" --remote-debugging-port=9333 --user-data-dir="$PROFILE" \
  --no-first-run --no-default-browser-check --disable-component-update \
  "https://login.alibaba.com/" >/tmp/aqc_edge.log 2>&1 &
EDGE_PID=$!
echo "Edge 已启动 PID=$EDGE_PID"
sleep 9

LOGGED=0
DEADLINE=$(( $(date +%s) + MAXWAIT ))
while true; do
  OUT=$("$NODE" scripts/probe_login.js "$PROBE_URL" 2>/dev/null | tail -1)
  echo "$(date +%H:%M:%S) $OUT"
  case "$OUT" in
    \[OK\]*) LOGGED=1; break ;;
    NOPORT)  echo "!!! 调试端口消失"; break ;;
  esac
  [ "$(date +%s)" -ge "$DEADLINE" ] && { echo "!!! 等登录超时"; break; }
  sleep 4
done

if [ "$LOGGED" != "1" ]; then
  echo "=== 未拿到登录态，跳过采集 ==="
  kill $EDGE_PID 2>/dev/null
  exit 3
fi

echo "=== 开始采集 ==="
"$NODE" scripts/collect_alibaba_v3.js "$LINKS"
echo "=== 补属性 ==="
"$NODE" scripts/retry_attrs.js "$LINKS"
echo "=== 收尾 ==="
kill $EDGE_PID 2>/dev/null
echo "done"
