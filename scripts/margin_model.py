#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""margin_model.py —— 报价毛利与净利测算（纯标准库）

两种用法：
    python margin_model.py --params params.csv [--json out.json]
    python margin_model.py --selftest

params.csv（key,value）：
    eq mat sw sv               四类金额（万元，不含税）
    r_eq r_mat r_sw r_sv        对应成本率（默认 0.90 / 0.85 / 0.40 / 0.55）
    r_install r_debug           安装与调试的成本率（默认 0.72 / 0.65）
    r_manage r_measure          管理与措施的成本率（默认 0.90 / 0.80）
    vat_out_credit              实缴增值税占销项的比例（默认 0.30）
    sga_rate                    公司管理费用占不含税造价比例（默认 0.06）
    advance_wan                 垫资额（万元，默认 550）
    advance_months              平均占用月数（默认 4.5）
    advance_rate                资金年化成本（默认 0.06）

输出：分类毛利表、毛利/净利、三情景敏感度；exit 0 正常，2 输入错误。
"""
import argparse, csv, json, os, sys

RATES = {
    "r_eq": 0.90, "r_mat": 0.85, "r_sw": 0.40, "r_sv": 0.55,
    "r_install": 0.72, "r_debug": 0.65, "r_manage": 0.90, "r_measure": 0.80,
}
FEE = {"install": 0.14, "debug": 0.05, "manage": 0.03, "measure": 0.04, "other": 0.05, "tax": 0.09}
COMMON = {"vat_out_credit": 0.30, "sga_rate": 0.06, "advance_wan": 550.0,
          "advance_months": 4.5, "advance_rate": 0.06}
SELF = {"eq": 750.61, "mat": 290.15, "sw": 203.84, "sv": 167.77}

# 三情景：乐观 / 中性 / 悲观 的成本率组合
SCENARIOS = {
    "乐观（自研软件+集采折扣）": {"r_eq": 0.88, "r_mat": 0.83, "r_sw": 0.35, "r_sv": 0.50},
    "中性（部分外购+折扣 5%）": {"r_eq": 0.90, "r_mat": 0.85, "r_sw": 0.40, "r_sv": 0.55},
    "悲观（全外购+无折扣+长质保）": {"r_eq": 0.95, "r_mat": 0.90, "r_sw": 0.70, "r_sv": 0.65,
                                     "r_install": 0.78, "r_debug": 0.72, "r_manage": 0.95, "r_measure": 0.85},
}


class InputError(Exception):
    pass


def load(path):
    p = {}
    if not path:
        return p
    if not os.path.exists(path):
        raise InputError("参数文件不存在：%s" % path)
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f)
        if not rd.fieldnames or "key" not in rd.fieldnames:
            raise InputError("参数文件需包含 key,value 两列")
        for row in rd:
            k = (row.get("key") or "").strip().lstrip("#").strip()
            v = (row.get("value") or "").strip()
            if not k or not v:
                continue
            try:
                p[k] = float(v)
            except ValueError:
                raise InputError("字段 %s 不是数字：%r" % (k, v))
    return p


def fee_chain(eq, mat, sw, sv):
    direct = eq + mat + sw + sv
    install = (eq + mat) * FEE["install"]
    debug = (eq + mat + sw) * FEE["debug"]
    manage = (direct + install + debug) * FEE["manage"]
    fbfx = direct + install + debug + manage
    measure = fbfx * FEE["measure"]
    other = fbfx * FEE["other"]
    pretax = fbfx + measure + other
    vat = pretax * FEE["tax"]
    return {"direct": direct, "install": install, "debug": debug, "manage": manage,
            "fbfx": fbfx, "measure": measure, "other": other,
            "pretax": pretax, "vat": vat, "total": pretax + vat}


def model(vals, rates, common):
    c = fee_chain(vals["eq"], vals["mat"], vals["sw"], vals["sv"])
    items = [("设备", vals["eq"], rates["r_eq"]), ("材料", vals["mat"], rates["r_mat"]),
             ("软件", vals["sw"], rates["r_sw"]), ("服务", vals["sv"], rates["r_sv"]),
             ("施工安装", c["install"], rates["r_install"]),
             ("系统调试", c["debug"], rates["r_debug"]),
             ("项目管理", c["manage"], rates["r_manage"]),
             ("措施项目", c["measure"], rates["r_measure"])]
    rows, rev, cost = [], 0.0, 0.0
    for name, price, cr in items:
        cc = price * cr
        rows.append((name, price, cr, cc, price - cc))
        rev += price
        cost += cc
    gross = rev - cost
    vat_paid = c["vat"] * common["vat_out_credit"]
    surtax = vat_paid * 0.12
    sga = c["pretax"] * common["sga_rate"]
    fin = common["advance_wan"] * (common["advance_months"] / 12.0) * common["advance_rate"]
    net = gross - vat_paid - surtax - sga - fin
    return {"chain": c, "rows": rows, "revenue": rev, "cost": cost,
            "gross": gross, "vat_paid": vat_paid, "surtax": surtax,
            "sga": sga, "fin": fin, "net": net}


def render(m, vals):
    c = m["chain"]
    L = ["=" * 64,
         "毛利测算（万元）　不含税造价 %.2f｜含税 %.2f" % (c["pretax"], c["total"]),
         "-" * 64,
         "%-10s%10s%9s%11s%10s%8s" % ("类别", "报价", "成本率", "成本", "毛利", "毛利率")]
    for name, price, cr, cc, gp in m["rows"]:
        L.append("%-10s%10.2f%8.0f%%%11.2f%10.2f%7.1f%%" % (name, price, cr * 100, cc, gp, gp / price * 100 if price else 0))
    L.append("-" * 64)
    L.append("%-10s%10.2f%9s%11.2f%10.2f%7.1f%%" % ("小计", m["revenue"], "", m["cost"], m["gross"], m["gross"] / m["revenue"] * 100))
    L.append("暂列金额 %.2f 万元（业主预备金，不计入毛利）" % c["other"])
    L.append("-" * 64)
    L.append("实缴增值税 %8.2f｜附加税 %6.2f｜公司管理费 %7.2f｜财务费用 %6.2f"
             % (m["vat_paid"], m["surtax"], m["sga"], m["fin"]))
    L.append("%-10s%10s%9s%11s%10.2f%7.1f%%" % ("净利", "", "", "", m["net"], m["net"] / c["pretax"] * 100))
    L.append("=" * 64)
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", default="")
    ap.add_argument("--json", default="")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    try:
        p = dict(SELF) if a.selftest else {}
        p.update(load(a.params))
        if not p:
            raise InputError("未提供金额：用 --params 或 --selftest")
        vals = {k: float(p.get(k, 0)) for k in ("eq", "mat", "sw", "sv")}
        rates = {k: float(p.get(k, v)) for k, v in RATES.items()}
        common = {k: float(p.get(k, v)) for k, v in COMMON.items()}
    except InputError as e:
        print("输入错误：%s" % e, file=sys.stderr)
        return 2

    base = model(vals, rates, common)
    out = [render(base, vals), "", "三情景敏感度（毛利率 / 净利率）", "-" * 64]
    table = {}
    for name, override in SCENARIOS.items():
        r = dict(rates)
        r.update({k: v for k, v in override.items()})
        mm = model(vals, r, common)
        table[name] = {"gross_margin": mm["gross"] / mm["revenue"] * 100,
                       "net_margin": mm["net"] / mm["chain"]["pretax"] * 100,
                       "net": round(mm["net"], 2)}
        out.append("%-24s %6.1f%% / %6.1f%%  净利 %8.2f"
                   % (name, table[name]["gross_margin"], table[name]["net_margin"], mm["net"]))
    text = "\n".join(out)
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.write(text.encode("utf-8", "replace").decode("utf-8", "replace"))

    if a.json:
        payload = {"chain": {k: round(v, 4) for k, v in base["chain"].items()},
                   "gross": round(base["gross"], 2), "net": round(base["net"], 2),
                   "gross_margin_pct": round(base["gross"] / base["revenue"] * 100, 2),
                   "net_margin_pct": round(base["net"] / base["chain"]["pretax"] * 100, 2),
                   "scenarios": table}
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print("报告已写出：%s" % a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())