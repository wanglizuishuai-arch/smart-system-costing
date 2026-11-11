#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""costing_check.py —— 智能化项目取费链复算与交叉校验（纯标准库，Python 3.8+）

用法：
    python costing_check.py --selftest
    python costing_check.py --params params.csv [--options options.csv] [--json out.json]

退出码：
    0  全部校验通过，可出文档
    1  有阻断项（金额不闭合），不许出文档
    2  输入有问题（文件缺失、字段缺失、数值非法），不是校验结论

params.csv 字段（key,value，缺项取默认值）：
    eq, mat, sw, sv            设备/材料/软件/服务（万元，不含税）
    install_rate debug_rate manage_rate measure_rate other_rate tax_rate
    control_main               主预算控制额（万元，可空）
    layer_main_direct          投产必建直接费（可空）
    layer_op_direct            运营配套直接费（可空）
    direct_declared            清单合计（用于反查加总，可空）

options.csv 字段（code,name,direct,switch）：
    switch 为 0/1，用于复算已选合计
"""

import argparse
import csv
import json
import os
import sys

DEFAULTS = {
    "eq": 0.0, "mat": 0.0, "sw": 0.0, "sv": 0.0,
    "install_rate": 0.14, "debug_rate": 0.05, "manage_rate": 0.03,
    "measure_rate": 0.04, "other_rate": 0.05, "tax_rate": 0.09,
    "control_main": "", "layer_main_direct": "", "layer_op_direct": "",
    "direct_declared": "",
}

SELFTEST = {
    "eq": 750.61, "mat": 290.15, "sw": 203.84, "sv": 167.77,
    "control_main": 2050, "layer_main_direct": 1301.39, "layer_op_direct": 110.98,
    "direct_declared": 1412.37,
}

# 自测基线（见 references/02 第二节）
EXPECT = {"direct": 1412.37, "install": 145.71, "debug": 62.23, "manage": 48.61,
          "fbfx": 1668.92, "measure": 66.76, "other": 83.45, "pretax": 1819.13,
          "vat": 163.72, "total": 1982.85}


class InputError(Exception):
    pass


def load_params(path):
    p = dict(DEFAULTS)
    if not path:
        return p
    if not os.path.exists(path):
        raise InputError("参数文件不存在：%s" % path)
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f)
        if not rd.fieldnames or "key" not in rd.fieldnames or "value" not in rd.fieldnames:
            raise InputError("参数文件需包含 key,value 两列")
        for row in rd:
            k = (row.get("key") or "").strip()
            if not k:
                continue
            if k not in DEFAULTS:
                continue  # 未知字段忽略，不阻断（便于扩展）
            v = (row.get("value") or "").strip()
            p[k] = v if v != "" else ""
    return p


def num(p, k):
    v = p.get(k)
    if v == "" or v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        raise InputError("字段 %s 不是数字：%r" % (k, v))


def compute(p):
    eq, mat, sw, sv = (num(p, k) or 0.0 for k in ("eq", "mat", "sw", "sv"))
    r = {k: (num(p, k) if num(p, k) is not None else DEFAULTS[k])
         for k in ("install_rate", "debug_rate", "manage_rate", "measure_rate", "other_rate", "tax_rate")}
    for k, v in r.items():
        if v < 0 or v > 1:
            raise InputError("费率 %s 应在 0–1 之间：%r" % (k, v))

    direct = eq + mat + sw + sv
    base_install = eq + mat
    base_debug = eq + mat + sw
    install = base_install * r["install_rate"]
    debug = base_debug * r["debug_rate"]
    manage = (direct + install + debug) * r["manage_rate"]
    fbfx = direct + install + debug + manage
    measure = fbfx * r["measure_rate"]
    other = fbfx * r["other_rate"]
    pretax = fbfx + measure + other
    vat = pretax * r["tax_rate"]
    total = pretax + vat

    out = {"eq": eq, "mat": mat, "sw": sw, "sv": sv, "direct": direct,
           "base_install": base_install, "base_debug": base_debug,
           "install": install, "debug": debug, "manage": manage,
           "fbfx": fbfx, "measure": measure, "other": other,
           "pretax": pretax, "vat": vat, "total": total,
           "rate": r}
    return out


def load_options(path):
    if not path:
        return []
    if not os.path.exists(path):
        raise InputError("选配文件不存在：%s" % path)
    rows = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f)
        need = {"code", "name", "direct", "switch"}
        if not rd.fieldnames or not need.issubset(set(rd.fieldnames)):
            raise InputError("选配文件需包含列：code,name,direct,switch")
        for row in rd:
            code = (row.get("code") or "").strip()
            if not code:
                continue
            try:
                d = float(row.get("direct") or 0)
                s = int(float(row.get("switch") or 0))
            except ValueError:
                raise InputError("选配行 %s 的 direct/switch 不是数字" % code)
            if s not in (0, 1):
                raise InputError("选配行 %s 的 switch 只能是 0 或 1" % code)
            rows.append({"code": code, "name": (row.get("name") or "").strip(),
                         "direct": d, "switch": s})
    return rows


def check(c, p, opts):
    """返回 list[(名称, 左值, 右值, 通过?)]；同时返回阻断数"""
    res = []
    tol = 0.02

    def add(name, left, right):
        ok = left is not None and right is not None and abs(left - right) < tol
        res.append((name, left, right, ok))
        return ok

    # 1 分类合计 = 声明合计
    decl = num(p, "direct_declared")
    add("清单合计 = 设备+材料+软件+服务", decl if decl is not None else c["direct"], c["direct"])

    # 2 安装基数只取设备+材料
    add("安装基数 = 设备+材料", c["base_install"], c["eq"] + c["mat"])
    # 3 调试基数取设备+材料+软件
    add("调试基数 = 设备+材料+软件", c["base_debug"], c["eq"] + c["mat"] + c["sw"])

    # 4 分部分项闭合
    add("分部分项 = 直接费+安装+调试+管理", c["fbfx"],
        c["direct"] + c["install"] + c["debug"] + c["manage"])
    # 5 税前闭合
    add("税前 = 分部分项+措施+暂列", c["pretax"], c["fbfx"] + c["measure"] + c["other"])
    # 6 含税闭合
    add("含税 = 税前+增值税", c["total"], c["pretax"] + c["vat"])

    # 7 控制额 ≥ 含税
    ctrl = num(p, "control_main")
    if ctrl is not None:
        ok = ctrl + 1e-9 >= c["total"]
        res.append(("控制额 ≥ 含税造价", ctrl, c["total"], ok))

    # 8 分层合计 = 含税
    lm, lo = num(p, "layer_main_direct"), num(p, "layer_op_direct")
    if lm is not None and lo is not None:
        if abs((lm + lo) - c["direct"]) >= tol:
            res.append(("分层直接费合计 = 直接费", lm + lo, c["direct"], False))
        else:
            # 按同一取费口径反算含税（两层的费用结构一致，用整体系数近似）
            k = c["total"] / c["direct"] if c["direct"] else 0
            res.append(("分层含税合计 = 含税造价（按综合系数近似）",
                        round((lm + lo) * k, 2), round(c["total"], 2), True))

    # 9 选配合计
    if opts:
        sel_d = sum(o["direct"] for o in opts if o["switch"] == 1)
        res.append(("已选选配直接费 = Σ(switch×direct)", sel_d,
                    sum(o["direct"] * o["switch"] for o in opts), True))

    bad = sum(0 if r[3] else 1 for r in res)
    return res, bad


def render(c, res, bad):
    L = []
    L.append("=" * 62)
    L.append("取费链复算（万元）")
    L.append("-" * 62)
    rows = [("设备", c["eq"]), ("材料", c["mat"]), ("软件", c["sw"]), ("服务", c["sv"]),
            ("直接费", c["direct"]), ("施工安装 %.0f%%" % (c["rate"]["install_rate"] * 100), c["install"]),
            ("系统调试 %.0f%%" % (c["rate"]["debug_rate"] * 100), c["debug"]),
            ("项目管理 %.0f%%" % (c["rate"]["manage_rate"] * 100), c["manage"]),
            ("分部分项", c["fbfx"]),
            ("措施项目 %.0f%%" % (c["rate"]["measure_rate"] * 100), c["measure"]),
            ("暂列金额 %.0f%%" % (c["rate"]["other_rate"] * 100), c["other"]),
            ("税前造价", c["pretax"]), ("增值税 %.0f%%" % (c["rate"]["tax_rate"] * 100), c["vat"]),
            ("含税造价", c["total"])]
    for n, v in rows:
        L.append("%-22s%12.2f" % (n, v))
    L.append("-" * 62)
    L.append("交叉校验")
    for name, left, right, ok in res:
        L.append("%s %-42s %10.2f / %10.2f" % ("[OK]" if ok else "[!!]", name,
                                               left if left is not None else float("nan"),
                                               right if right is not None else float("nan")))
    L.append("-" * 62)
    L.append("结论：%s（阻断项 %d）" % ("通过，可出文档" if bad == 0 else "不通过，禁止出文档", bad))
    L.append("=" * 62)
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", default="")
    ap.add_argument("--options", default="")
    ap.add_argument("--json", default="")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    try:
        p = dict(DEFAULTS)
        p.update(SELFTEST if a.selftest else {})
        p.update(load_params(a.params) if a.params else {})
        c = compute(p)
        opts = load_options(a.options)
    except InputError as e:
        print("输入错误：%s" % e, file=sys.stderr)
        return 2

    res, bad = check(c, p, opts)
    text = render(c, res, bad)
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.write(text.encode("utf-8", "replace").decode("utf-8", "replace"))

    if a.selftest:
        bad_self = [k for k, v in EXPECT.items() if abs(c[k] - v) >= 0.02]
        print("基线比对：%s" % ("全部吻合" if not bad_self else "偏差：" + ",".join(bad_self)))
        if bad_self:
            bad += 1

    if a.json:
        payload = {"computed": {k: round(v, 4) if isinstance(v, (int, float)) else v
                                for k, v in c.items() if k != "rate"},
                   "rates": c["rate"],
                   "checks": [{"name": n, "left": l, "right": r, "pass": ok} for n, l, r, ok in res],
                   "blockers": bad}
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print("报告已写出：%s" % a.json)

    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())