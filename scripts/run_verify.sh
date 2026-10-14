#!/usr/bin/env bash
# run_verify.sh — 一条命令里跑完「起静态服务 + 开 Edge + 真实浏览器验证 + 收尾」
#
# ⚠️ 本环境 bash 每次调用结束会回收子进程和 localhost 端口，
#    跨调用连不上 127.0.0.1:9333 / 8899，所以这三件事必须在**同一次调用**里完成。
#
# 用法：bash scripts/run_verify.sh [传给 verify_new_product_images.js 的过滤词]
set -u

EDGE="/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
NODE="C:/Users/Administrator/.workbuddy/binaries/node/versions/22.22.2-6/node.exe"
PROFILE="C:/Users/Administrator/AppData/Local/Temp/aqcedge3"

cd "C:/Users/Administrator/.qclaw/workspace/aquaclean-home" || exit 1

"$EDGE" --remote-debugging-port=9333 --user-data-dir="$PROFILE" \
  --no-first-run --no-default-browser-check --disable-component-update \
  "about:blank" >/tmp/aqc_edge_verify.log 2>&1 &
EDGE_PID=$!
python -m http.server 8899 --bind 127.0.0.1 >/tmp/aqc_http.log 2>&1 &
HTTP_PID=$!

sleep 8
curl -s --noproxy '*' --max-time 5 http://127.0.0.1:9333/json/version | head -2
curl -s --noproxy '*' --max-time 5 http://127.0.0.1:8899/en/index.html -o /dev/null -w "http=%{http_code}\n"

"$NODE" scripts/verify_new_product_images.js "$@"
RC=$?

kill $HTTP_PID 2>/dev/null
kill $EDGE_PID 2>/dev/null
echo "verify exit=$RC"
exit $RC
