#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""split_layers.py —— 按关键词把清单拆成「投产必建 / 运营配套」，并给出分层取费

分层判据（可按项目改 KEYWORDS）：
    运营配套：会议、培训、直播、信息发布、研学、沙盘、展厅、大屏（非指挥中心）
    其余 → 投产必建

用法：
    python split_layers.py --boq examples/items.csv [--json out.json]
    python split_layers.py --selftest
"""
import argparse, csv, json, os, sys

KEYWORDS = ["会议", "培训", "直播", "信息发布", "发布屏", "研学", "沙盘", "展厅", "多媒体", "门厅屏"]
FEE = {"install": 0.14, "debug": 0.05, "manage": 0.03, "measure": 0.04, "other": 0.05, "tax": 0.09}


class InputError(Exception):
    pass


def load(path):
    if not os.path.exists(path):
        raise InputError("清单不存在：%s" % path)
    rows = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f)
        cols = set(rd.fieldnames or [])
        if not {"类别", "项目"}.issubset(cols):
            raise InputError("清单需包含「类别」「项目」列")
        full = {"数量", "单价"}.issubset(cols)
        for i, r in enumerate(rd, 2):
            try:
                amt = (float(r.get("数量") or 0) * float(r.get("单价") or 0) / 10000.0
                       if full else float(r.get("金额") or 0))
            except ValueError:
                raise InputError("第%d行金额不是数字" % i)
            rows.append({"cat": (r.get("类别") or "").strip(),
                         "name": (r.get("项目") or "").strip(),
                         "amount": amt,
                         "type": (r.get("类型") or "").strip() or "设备"})
    if not rows:
        raise InputError("清单为空")
    return rows


def layer_of(name, cat):
    blob = (name or "") + (cat or "")
    return "运营配套" if any(k in blob for k in KEYWORDS) else "投产必建"


def fee(direct, install_share=0.74, debug_share=0.86):
    """单层取费：install_share=设备材料占直接费比例，debug_share=设备材料软件占比"""
    inst = direct * install_share * FEE["install"]
    dbg = direct * debug_share * FEE["debug"]
    mng = (direct + inst + dbg) * FEE["manage"]
    fb = direct + inst + dbg + mng
    return fb * (1 + FEE["measure"] + FEE["other"]) * (1 + FEE["tax"])


def run(rows):
    buckets = {}
    for r in rows:
        lay = layer_of(r["name"], r["cat"])
        b = buckets.setdefault(lay, {"direct": 0.0, "items": []})
        b["direct"] += r["amount"]
        b["items"].append(r)
    for lay, b in buckets.items():
        b["direct"] = round(b["direct"], 2)
        b["total"] = round(fee(b["direct"]), 2)
    return buckets


def render(buckets):
    total_d = sum(b["direct"] for b in buckets.values())
    L = ["=" * 66, "分层拆分（万元）　合计直接费 %.2f" % total_d, "-" * 66,
         "%-10s%10s%12s%8s%8s" % ("层次", "直接费", "含税造价", "占比", "条目")]
    for lay in ("投产必建", "运营配套"):
        b = buckets.get(lay)
        if not b:
            continue
        L.append("%-10s%10.2f%12.2f%7.1f%%%8d"
                 % (lay, b["direct"], b["total"], b["direct"] / total_d * 100, len(b["items"])))
    L.append("-" * 66)
    op = buckets.get("运营配套")
    if op:
        L.append("运营配套包含：" + "、".join(sorted({i["name"] for i in op["items"]})[:10]))
        L.append("说明：可随房间装修/经营节奏后置；投产必建必须与土建同步。")
    L.append("=" * 66)
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--boq", default="")
    ap.add_argument("--json", default="")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    try:
        if a.selftest:
            rows = [{"cat": "会议", "name": "报告厅音视频", "amount": 28.5, "type": "设备"},
                    {"cat": "信息发布", "name": "入口LED屏", "amount": 12.1, "type": "设备"},
                    {"cat": "网络", "name": "核心交换机", "amount": 12.0, "type": "设备"},
                    {"cat": "农业", "name": "温室控制柜", "amount": 67.5, "type": "设备"}]
        else:
            if not a.boq:
                raise InputError("需要 --boq 或 --selftest")
            rows = load(a.boq)
    except InputError as e:
        print("输入错误：%s" % e, file=sys.stderr)
        return 2

    buckets = run(rows)
    text = render(buckets)
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.write(text.encode("utf-8", "replace").decode("utf-8", "replace"))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump({k: {"direct": v["direct"], "total": v["total"], "count": len(v["items"])}
                       for k, v in buckets.items()}, f, ensure_ascii=False, indent=2)
        print("报告已写出：%s" % a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())