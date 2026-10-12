#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_admin_data_from_public.py — 把公开站的 data/ 同步到内容后台的 data/。

为什么需要它
------------
后台（aquaclean-admin-app）里的 data/ 是公开站 data/ 的一份旧拷贝，拷贝之后两边
各自演化，后台一直没跟上：

  * 2026-10-08 全站换公司主体，后台的 data/ 还是旧公司名 / 旧电话 / 旧邮箱；
  * 2026-10-12 修好了 products/*.json 里被 7f09acc 弄坏的 highlights
    （以及 gt20 的 specs / quick_specs），后台还是坏的。

而后台的产品编辑器正是从**自己的** /data/products/<cat>.json 预填充表单的
（admin/admin.js: "Fetch from live site" 那段，XHR 打 /data/products/...）。
所以光修公开站不够：从后台点一次「🚀 发布到线上」，表单里带的还是旧公司名和
坏亮点，会被 merge 回 GitHub 里那个好文件，把刚修好的东西重新弄坏。

为什么不做"重新跑 build_admin_app.py"
----------------------------------
试过，不行，那个脚本已经过期而且危险：
  * 它 `shutil.rmtree(OUT)` 整个输出目录，会删掉只存在于后台目录里的
    inquiry-proxy.html —— 而公开站的询盘中继（assets/js/inquiry-sink.js）
    硬编码指着 https://aquaclean-admin.app.workbuddy.host/inquiry-proxy.html，
    删了线上询盘直接瘫。
  * 它从 aquaclean-home/admin/ 拷 admin.js / dashboard.html / login.html /
    index.html，但公开站那个 admin/ 目录里放的是 /admin/ 重定向页（各 1345B）
    和一份 10-06 的旧 admin.js（99404B）；真正在跑的后台文件更大更新
    （admin.js 108482B、dashboard.html 51412B），只存在于后台目录、没有进 git。
    跑一遍等于用旧代码覆盖新代码。

所以这里做**外科手术式同步**：只动 data/，逐个文件覆盖，其余一律不碰。

安全策略
--------
默认 dry-run，只报告不写文件；--apply 才写。写之前自动整树备份。

三道闸门，任何一道不过就拒绝 apply（退出码 2）并说清楚原因：

  G1 文件清单一致：两边 data/ 的文件集合必须完全相同。
     只出现在一边的文件只报告、不动，但只要有就直接退出。

  G2 差异必须可解释：逐叶子比较，每一处差异都必须落进下面几种"已知漂移"之一，
     落不进去的一律算 UNKNOWN，对应文件跳过不写：
       - identity       路径或任意一侧的值里含已知公司主体字符串
       - field-drift    company.json 的 /founded /headquarters、
                        contact.json 的 /address（2026-10-08 主体更新的一部分）
       - corrupt        products/*.json 里 /highlights 下的差异
                        （7f09acc 把整个 products 数组塞进了第一个产品的
                        highlights，后台带着这个损坏）
       - corrupt-specs  KNOWN_CORRUPT_SPECS 里那对 (产品 id, 字段)
                        —— gt20 的 specs / quick_specs 被同一个 commit
                        分别塞成了 reviews 数组和 review schema
     出现 UNKNOWN 说明两边有讲清楚的第三种变化，必须先人工确认再放行。

  G3 写完之后复核：每个文件的规范化内容必须与公开站逐字节相同，
     且每个文件的主导换行符必须和写之前一致（不把混合换行整体翻面）。

换行符
------
两边都是混合换行（后台 21 LF / 33 CRLF，公开站 41 LF / 13 CRLF）。
逐个文件看主导风格：目标文件按**后台原文件**的主导换行符输出，
公开站内容先规范成 LF 再按需转成 CRLF。这样 diff 最小，也不会把
CRLF 文件悄悄变成 LF。

用法
----
  python scripts/sync_admin_data_from_public.py              # 预演
  python scripts/sync_admin_data_from_public.py --apply      # 备份并写入
  python scripts/sync_admin_data_from_public.py --no-backup  # 搭配 --apply，
                                                             # 跳过自动备份
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

DEFAULT_PUBLIC_DATA = os.path.join(ROOT, "data")
DEFAULT_ADMIN_DATA = os.path.join(ROOT, "..", "aquaclean-admin-app", "data")

# ── 已知的公司主体字符串（2026-10-08 全站替换的两套值） ─────────────────
IDENTITY_TOKENS = [
    "AquaClean Home Appliances Co., Ltd.",   # 旧
    "Hong Kong Damaijia Technology Co., Limited",  # 新
    "info@aquaclean-home.com",               # 旧
    "postmaster@hkdmj.net",                  # 新
    "+86 177 7919 0118",                     # 旧
    "+86 16599999117",                       # 新
    "aquaclean-home.com",
    "hkdmj.net",
]

# company.json / contact.json 里属于同一次主体更新、但不含上述字符串的字段
KNOWN_FIELD_DRIFT = {
    "company.json": {"/founded", "/headquarters"},
    "contact.json": {"/address"},
}

# 7f09acc 除了弄坏每个类目第一个产品的 highlights，还把 gt20 的
# specs 塞成了 reviews 数组、quick_specs 塞成了 review schema。
# 公开站已在 1d54ccd 修好，后台还是坏的。
KNOWN_CORRUPT_SPECS = {("gt20", "specs"), ("gt20", "quick_specs")}

CORRUPT_HIGHLIGHTS_MARK = "/highlights"


def norm(b: bytes) -> bytes:
    """规范换行：CRLF / 单独 CR 都归一成 LF，用于"内容相同"的判定。"""
    return b.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def dominant_eol(b: bytes) -> bytes:
    """文件的主导换行符。JSON 里不可能出现裸 CR（控制字符必须转义），
    所以 CRLF 一定是行尾、不是字符串内容，这样统计是安全的。"""
    crlf = b.count(b"\r\n")
    lf = b.count(b"\n") - crlf
    return b"\r\n" if crlf > lf else b"\n"


def read_bytes(p: str) -> bytes:
    with open(p, "rb") as f:
        return f.read()


def write_bytes(p: str, b: bytes) -> None:
    # 写文件的安全习惯：先算好内容、断言非空，再开写。
    # （早先踩过 io.open(p,'w').write(...) 的坑：Python 先求值 open 就把文件
    #  清空了，后面表达式一抛异常，文件就变 0 字节。）
    assert isinstance(b, (bytes, bytearray)) and len(b) > 0, "拒绝写入空内容: %s" % p
    with open(p, "wb") as f:
        f.write(b)


def leaves(v, prefix=""):
    """递归取所有叶子，返回 {路径: 值}。dict 走键，list 走下标。"""
    out = {}
    if isinstance(v, dict):
        for k, sub in v.items():
            out.update(leaves(sub, prefix + "/" + str(k)))
    elif isinstance(v, list):
        for i, sub in enumerate(v):
            out.update(leaves(sub, prefix + "[" + str(i) + "]"))
    else:
        out[prefix] = v
    return out


def product_leaves(j) -> dict:
    """products/*.json 专用：按产品 id 对齐后再取叶子，路径形如 /<id>/<字段>...

    不能直接用数组下标：两边第一个产品的 highlights 一个坏一个好，长度差很多，
    下标会把后面所有产品的路径全部错开，做不出有意义的逐条比较。
    """
    out = {}
    plist = j.get("products")
    if not isinstance(plist, list):
        return leaves(j)
    for p in plist:
        if not isinstance(p, dict):
            continue
        pid = str(p.get("id", "?"))
        out.update(leaves(p, "/" + pid))
    for k in j:
        if k == "products":
            continue
        out.update(leaves(j[k], "/<top:" + str(k) + ">"))
    return out


def ident_related(s: str) -> bool:
    return any(tok in s for tok in IDENTITY_TOKENS)


def classify(rel: str, path: str, pub_v, adm_v) -> str:
    """给一处差异归类。返回 'identity' / 'field-drift' / 'corrupt' /
    'corrupt-specs' / 'unknown'。"""
    if rel in KNOWN_FIELD_DRIFT and path in KNOWN_FIELD_DRIFT[rel]:
        return "field-drift"
    if ident_related(path) or ident_related(str(pub_v)) or ident_related(str(adm_v)):
        return "identity"
    if rel.startswith("products/"):
        if CORRUPT_HIGHLIGHTS_MARK in path:
            return "corrupt"
        # path 形如 /<pid>/specs[13]/label/ru，第二段可能带着数组下标，
        # 先把 [..] 摘掉再当字段名比。
        segs = [s for s in path.split("/") if s]
        if len(segs) >= 2:
            pid, field = segs[0], segs[1].split("[")[0]
            if (pid, field) in KNOWN_CORRUPT_SPECS:
                return "corrupt-specs"
    return "unknown"


def eol_style(b: bytes) -> str:
    return "CRLF" if dominant_eol(b) == b"\r\n" else "LF"


def main() -> int:
    ap = argparse.ArgumentParser(
        description="把公开站 data/ 同步到内容后台 data/（默认预演）")
    ap.add_argument("--apply", action="store_true", help="实际写入（否则只报告）")
    ap.add_argument("--no-backup", action="store_true",
                    help="--apply 时跳过自动备份（不推荐）")
    ap.add_argument("--public-data", default=DEFAULT_PUBLIC_DATA)
    ap.add_argument("--admin-data", default=DEFAULT_ADMIN_DATA)
    ap.add_argument("--backup-root",
                    default=os.path.dirname(DEFAULT_ADMIN_DATA),
                    help="自动备份的存放根目录（默认在后台应用目录的旁边，"
                         "绝不能放在应用目录里面，否则会被一起发布出去）")
    args = ap.parse_args()

    pub_root = os.path.abspath(args.public_data)
    adm_root = os.path.abspath(args.admin_data)
    if not os.path.isdir(pub_root):
        print("❌ 公开站 data/ 不存在: %s" % pub_root)
        return 1
    if not os.path.isdir(adm_root):
        print("❌ 后台 data/ 不存在: %s" % adm_root)
        return 1

    def walk(root):
        out = []
        for dp, _dn, fn in os.walk(root):
            for f in fn:
                rel = os.path.relpath(os.path.join(dp, f), root).replace("\\", "/")
                out.append(rel)
        return sorted(out)

    pub_files, adm_files = walk(pub_root), walk(adm_root)

    # ── G1：文件清单一致 ────────────────────────────────────────────
    only_pub = sorted(set(pub_files) - set(adm_files))
    only_adm = sorted(set(adm_files) - set(pub_files))
    print("公开站 data/ : %s  (%d 个文件)" % (pub_root, len(pub_files)))
    print("后台   data/ : %s  (%d 个文件)" % (adm_root, len(adm_files)))
    if only_pub or only_adm:
        print("\n❌ G1 不过：两边文件清单不一致")
        for r in only_pub:
            print("   仅公开站有: %s" % r)
        for r in only_adm:
            print("   仅后台有  : %s" % r)
        print("   清单不一致时不做任何写入，请先人工确认。")
        return 2
    print("G1 ✅ 文件清单一致（%d 个）" % len(pub_files))

    # ── 逐文件比较 + G2 差异分类 ────────────────────────────────────
    plans = []          # (rel, 新内容 bytes, 原主导换行符, 统计)
    same = 0
    blocked = []        # (rel, [unknown 差异...])
    totals = {"identity": 0, "field-drift": 0, "corrupt": 0,
              "corrupt-specs": 0, "unknown": 0}

    for rel in pub_files:
        p_pub, p_adm = os.path.join(pub_root, rel), os.path.join(adm_root, rel)
        b_pub_raw, b_adm_raw = read_bytes(p_pub), read_bytes(p_adm)
        b_pub, b_adm = norm(b_pub_raw), norm(b_adm_raw)
        if b_pub == b_adm:
            same += 1
            continue

        try:
            j_pub = json.loads(b_pub.decode("utf-8"))
            j_adm = json.loads(b_adm.decode("utf-8"))
        except Exception as e:  # 解析失败本身就是事故，必须停下来
            print("\n❌ %s 不是合法 JSON: %s" % (rel, e))
            return 2

        if rel.startswith("products/") and rel.endswith(".json") \
                and os.path.basename(rel) != "categories.json":
            lp, la = product_leaves(j_pub), product_leaves(j_adm)
        else:
            lp, la = leaves(j_pub), leaves(j_adm)

        buckets = {}
        unknowns = []
        for k in set(lp) | set(la):
            if lp.get(k) == la.get(k):
                continue
            cls = classify(rel, k, lp.get(k), la.get(k))
            buckets[cls] = buckets.get(cls, 0) + 1
            if cls == "unknown":
                unknowns.append((k, lp.get(k), la.get(k)))

        for k, v in buckets.items():
            totals[k] = totals.get(k, 0) + v

        if unknowns:
            blocked.append((rel, unknowns))
            print("  ⛔ %-40s 有 %d 处无法归类的差异，跳过不写"
                  % (rel, len(unknowns)))
            for k, pv, av in unknowns[:8]:
                print("       UNKNOWN %s\n         公开站=%r\n         后台  =%r"
                      % (k, pv, av))
            if len(unknowns) > 8:
                print("       ... 其余 %d 处略" % (len(unknowns) - 8))
            continue

        # 目标内容：公开站内容（LF）+ 后台原文件的主导换行符
        eol = dominant_eol(b_adm_raw)
        out = b_pub if eol == b"\n" else b_pub.replace(b"\n", b"\r\n")
        plans.append((rel, out, eol_style(b_adm_raw), buckets))

    print("\n比较结果：%d 个文件，%d 个相同，%d 个需要写入，%d 个被闸门拦下"
          % (len(pub_files), same, len(plans), len(blocked)))
    print("差异归类合计：")
    for k in ("identity", "field-drift", "corrupt", "corrupt-specs", "unknown"):
        print("   %-14s %6d" % (k, totals.get(k, 0)))

    if blocked:
        print("\n❌ G2 不过：有 %d 个文件存在无法归类的差异" % len(blocked))
        print("   这说明两边出现了本脚本不知道的第三种变化。先人工确认这些差异")
        print("   该以哪边为准，再决定是否放行；不要直接 --apply。")
        return 2
    print("G2 ✅ 全部差异可归入已知漂移")

    # ── 亮点健康检查（不管有没有文件要写，都查一遍） ──────────────────
    print("\n附：确认曾被 7f09acc 损坏的产品亮点已恢复正常结构 ...")
    n_ok, n_bad = 0, []
    for rel in sorted(os.listdir(os.path.join(adm_root, "products"))):
        if not rel.endswith(".json") or rel == "categories.json":
            continue
        try:
            j = json.loads(norm(read_bytes(os.path.join(adm_root, "products", rel)))
                           .decode("utf-8"))
        except Exception as e:
            n_bad.append("%s（JSON 解析失败：%s）" % (rel, e))
            continue
        for p in j.get("products", []):
            hl = p.get("highlights")
            # 健康的亮点长这样：{"icon": "...", "text": {"en": ..., "zh": ...}}
            # 损坏时长这样：整个 products 数组被塞进来，第一项是另一个产品对象
            ok = (isinstance(hl, list) and len(hl) > 0
                  and isinstance(hl[0], dict)
                  and isinstance(hl[0].get("text"), dict)
                  and bool(hl[0]["text"].get("en"))
                  and "icon" in hl[0])
            if ok:
                n_ok += 1
            else:
                n_bad.append("%s / %s" % (rel, p.get("id")))
    print("   highlights 结构正常：%d 个产品" % n_ok)
    for b in n_bad:
        print("   ⚠ 仍不正常：%s" % b)

    if not plans:
        print("\n无事可做，两边 data/ 已经一致。")
        return 0

    print("\n计划写入 %d 个文件：" % len(plans))
    for rel, _out, eol, buckets in plans:
        detail = " ".join("%s=%d" % (k, v) for k, v in sorted(buckets.items()))
        print("   %-40s 保留原换行风格 %-4s  %s" % (rel, eol, detail))

    if not args.apply:
        print("\n（预演模式，未写任何文件。加 --apply 才会真正写入。）")
        return 0

    # ── 备份 ────────────────────────────────────────────────────────
    # 备份必须落在后台应用目录**外面**：这目录是要被整包发布出去的，
    # 把备份塞进去等于把旧数据一起推到线上。（第一版就犯过这个错。）
    if not args.no_backup:
        ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        bak = os.path.join(args.backup_root, "_admin_data_backup_" + ts)
        shutil.copytree(adm_root, os.path.join(bak, "data"))
        n = sum(len(f) for _d, _s, f in os.walk(os.path.join(bak, "data")))
        print("\n已备份后台 data/ -> %s （%d 个文件）" % (bak, n))

    # ── 写入 ────────────────────────────────────────────────────────
    print("\n写入中 ...")
    for rel, out, eol, _b in plans:
        p_adm = os.path.join(adm_root, rel)
        os.makedirs(os.path.dirname(p_adm), exist_ok=True)
        write_bytes(p_adm, out)
        # 写回来必须还是合法 JSON，且换行风格没变
        back = read_bytes(p_adm)
        json.loads(norm(back).decode("utf-8"))
        assert eol_style(back) == eol, "换行风格被改变: %s" % rel
        assert norm(read_bytes(os.path.join(pub_root, rel))) == norm(back), \
            "写完后与公开站不一致: %s" % rel
        print("   ✅ %s" % rel)

    # ── G3：整体复核 ────────────────────────────────────────────────
    print("\nG3 复核 ...")
    bad = []
    for rel in pub_files:
        b_pub = norm(read_bytes(os.path.join(pub_root, rel)))
        b_adm = norm(read_bytes(os.path.join(adm_root, rel)))
        if b_pub != b_adm:
            bad.append(rel)
    zero = [rel for rel in pub_files
            if os.path.getsize(os.path.join(adm_root, rel)) == 0]
    if bad or zero:
        print("❌ G3 不过：")
        for r in bad:
            print("   仍与公开站不一致: %s" % r)
        for r in zero:
            print("   0 字节文件: %s" % r)
        return 2
    print("G3 ✅ %d 个文件全部与公开站逐字节一致（换行归一后）" % len(pub_files))

    print("\n完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
