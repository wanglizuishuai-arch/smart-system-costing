#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""reconcile.py —— 两份报价的对账：同口径归一 + 逐类差额 + 差异归因

用途：两份清单（我方 / 对方）逐类对照，回答"差多少、差在哪三块、真实差价是多少"。

用法：
    python reconcile.py --mine mine.csv --theirs theirs.csv \
        [--theirs-normalize 1.22] [--json out.json]

    python reconcile.py --selftest

清单 CSV 列（两种都支持）：
    类别,项目,金额                 （金额单位万元）
    类别,项目,单位,数量,单价,类型   （按 数量×单价/10000 汇总）

--theirs-normalize：把对方金额折到与我方同口径的系数。
    对方"含税综合单价（含安装）"，我方"不含税不含安装" → 除 1.09（税）× 1.12（安装）≈ 1.22。
    只做一次除法，不做别的调整，避免"越算越像"。

输出：逐类表 + 三块最大差额 + 真实差价结论。exit 0 正常，2 输入错误。
"""
import argparse, csv, os, sys


class InputError(Exception):
    pass


def load(path):
    if not os.path.exists(path):
        raise InputError("文件不存在：%s" % path)
    rows = {}
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f)
        cols = set(rd.fieldnames or [])
        if "类别" not in cols:
            raise InputError("%s 缺少「类别」列" % path)
        full = {"数量", "单价"}.issubset(cols)
        if not full and "金额" not in cols:
            raise InputError("%s 需有「金额」列或「数量」「单价」列" % path)
        for i, r in enumerate(rd, 2):
            cat = (r.get("类别") or "未分类").strip()
            name = (r.get("项目") or "").strip()
            try:
                if full:
                    amt = float(r.get("数量") or 0) * float(r.get("单价") or 0) / 10000.0
                else:
                    amt = float(r.get("金额") or 0)
            except ValueError:
                raise InputError("%s 第%d行金额不是数字" % (path, i))
            rows.setdefault(cat, {"amount": 0.0, "items": []})
            rows[cat]["amount"] += amt
            if name:
                rows[cat]["items"].append((name, round(amt, 2)))
    if not rows:
        raise InputError("%s 没有任何有效行" % path)
    return rows


def compare(mine, theirs, k):
    cats = sorted(set(mine) | set(theirs))
    rows, top = [], []
    for c in cats:
        a = mine.get(c, {}).get("amount", 0.0)
        b_raw = theirs.get(c, {}).get("amount", 0.0)
        b = b_raw / k if k else b_raw
        d = a - b
        ratio = (a / b) if b > 0.0001 else None
        rows.append({"cat": c, "mine": a, "theirs_raw": b_raw, "theirs": b, "diff": d, "ratio": ratio})
        top.append((d, c))
    top.sort(reverse=True)
    return rows, top[:3]


def render(rows, top, k, ta, tb):
    L = ["=" * 74,
         "逐类对账（万元）　对方归一系数 ÷%.2f" % k,
         "-" * 74,
         "%-16s%10s%11s%10s%9s%7s" % ("类别", "我方", "对方(原)", "对方(归一)", "差额", "倍数")]
    for r in rows:
        L.append("%-16s%10.2f%11.2f%10.2f%9.2f%s"
                 % (r["cat"], r["mine"], r["theirs_raw"], r["theirs"], r["diff"],
                    ("%6.2fx" % r["ratio"]) if r["ratio"] else "     —"))
    L.append("-" * 74)
    L.append("%-16s%10.2f%11.2f%10.2f%9.2f" % ("合计", ta, tb, tb / k if k else tb, ta - (tb / k if k else tb)))
    L.append("-" * 74)
    L.append("差额最大的三块：")
    for d, c in top:
        L.append("  %-16s +%8.2f" % (c, d))
    ratio = (ta / (tb / k)) if tb and k else None
    L.append("-" * 74)
    if ratio:
        L.append("真实差价：同口径下我方是对方的 %.2f 倍（%+.1f%%）" % (ratio, (ratio - 1) * 100))
        if ratio >= 1.6:
            L.append("判断：倍数 ≥1.6，说明差异主要来自**范围与密度**，不能按单价直比；")
            L.append("      先逐类砍项对齐（见 references/04 第二节），再比单价。")
        elif ratio >= 1.15:
            L.append("判断：倍数 1.15–1.6，属于**选型档次**差异；能逐项说明差在哪，可正面比价。")
        else:
            L.append("判断：倍数 <1.15，同口径下价格相当；胜负在条款与服务，不在价格。")
    L.append("=" * 74)
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mine", default="")
    ap.add_argument("--theirs", default="")
    ap.add_argument("--theirs-normalize", type=float, default=1.22)
    ap.add_argument("--json", default="")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    try:
        if a.selftest:
            mine = {"机房": {"amount": 125.85, "items": []}, "平台": {"amount": 132.96, "items": []},
                    "布线": {"amount": 174.10, "items": []}, "视频": {"amount": 90.45, "items": []}}
            theirs = {k: {"amount": v["amount"] * 0.55, "items": []} for k, v in mine.items()}
        else:
            if not a.mine or not a.theirs:
                raise InputError("需要 --mine 与 --theirs")
            mine, theirs = load(a.mine), load(a.theirs)
        k = a.theirs_normalize
        if k <= 0:
            raise InputError("--theirs-normalize 必须 > 0")
    except InputError as e:
        print("输入错误：%s" % e, file=sys.stderr)
        return 2

    ta = sum(v["amount"] for v in mine.values())
    tb = sum(v["amount"] for v in theirs.values())
    rows, top = compare(mine, theirs, k)
    text = render(rows, top, k, ta, tb)
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.write(text.encode("utf-8", "replace").decode("utf-8", "replace"))

    if a.json:
        import json
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump({"normalize": k, "rows": rows,
                       "total_mine": round(ta, 2), "total_theirs": round(tb, 2),
                       "top3": [{"cat": c, "diff": round(d, 2)} for d, c in top]},
                      f, ensure_ascii=False, indent=2)
        print("报告已写出：%s" % a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())