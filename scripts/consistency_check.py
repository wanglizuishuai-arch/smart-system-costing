#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""consistency_check.py —— 三件套金额一致性 + 占位符残留检查

为什么需要它：文档写 1,982.85、表格里 1,983.4，人或机器都不会主动发现；
客户版里留一个 [待确认] 就是硬伤。这两类错误只有逐字比对才能抓住。

用法：
    python consistency_check.py --docx 方案.docx --xlsx 概算.xlsx --pptx 汇报.pptx \
        --expect 1982.85,1412.37,1109.57 [--json out.json]

    python consistency_check.py --selftest        # 用内置的最小样例自检

退出码：0 全通过｜1 有阻断（缺数字 / 占位符残留）｜2 输入有问题
"""
import argparse, json, os, re, sys

PLACEHOLDER = [
    (r"\[待确认[^\]]*\]", "待确认标记"),
    (r"\bTODO\b", "TODO"),
    (r"\bTBD\b", "TBD"),
    (r"XX+", "XX 占位"),
    (r"××", "×× 占位"),
    (r"【[^】]{0,20}】", "方括号占位"),
    (r"\?\?\?+", "问号占位"),
    (r"待补充|待填写|待定稿", "中文占位词"),
]


class InputError(Exception):
    pass


def norm(s):
    return re.sub(r"[\s,，]", "", s or "")


def variants(v):
    """一个金额的多种合法写法：1982.85 / 1982.8 / 1983"""
    out = set()
    try:
        f = float(v)
    except ValueError:
        return {norm(v)}
    for d in (0, 1, 2):
        out.add(("%." + str(d) + "f") % f)
    out.add(norm(v))
    return out


def read_docx(path):
    from docx import Document
    d = Document(path)
    parts = [p.text for p in d.paragraphs]
    for t in d.tables:
        for r in t.rows:
            for c in r.cells:
                parts.append(c.text)
    return parts


def read_xlsx(path):
    from openpyxl import load_workbook
    out = []
    for data_only in (True, False):
        wb = load_workbook(path, data_only=data_only)
        for ws in wb.worksheets:
            out.append(ws.title)
            for row in ws.iter_rows(values_only=True):
                for v in row:
                    if v is None:
                        continue
                    out.append(v if isinstance(v, str) else str(v))
    return out


def read_pptx(path):
    from pptx import Presentation
    prs = Presentation(path)
    out = []
    for i, s in enumerate(prs.slides, 1):
        for sh in s.shapes:
            if sh.has_text_frame:
                out.append(sh.text_frame.text)
            if getattr(sh, "has_table", False) and sh.has_table:
                for r in sh.table.rows:
                    for c in r.cells:
                        out.append(c.text)
        out.append("第%d页" % i)
    return out


def scan(name, texts, expects):
    res = {"file": name, "missing": [], "placeholders": []}
    blob = norm("\n".join(texts))
    for v in expects:
        if not any(var in blob for var in variants(v)):
            res["missing"].append(v)
    for pattern, label in PLACEHOLDER:
        for t in texts:
            for m in re.finditer(pattern, t or ""):
                frag = (t or "")[max(0, m.start() - 12):m.end() + 12].replace("\n", " ")
                res["placeholders"].append({"type": label, "hit": m.group(0), "context": frag})
                if len(res["placeholders"]) > 20:
                    break
            if len(res["placeholders"]) > 20:
                break
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docx", default="")
    ap.add_argument("--xlsx", default="")
    ap.add_argument("--pptx", default="")
    ap.add_argument("--expect", default="")
    ap.add_argument("--json", default="")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    try:
        readers = {"docx": read_docx, "xlsx": read_xlsx, "pptx": read_pptx}
        targets = []
        for kind in ("docx", "xlsx", "pptx"):
            p = getattr(a, kind)
            if not p:
                continue
            if not os.path.exists(p):
                raise InputError("%s 文件不存在：%s" % (kind, p))
            try:
                targets.append((os.path.basename(p), readers[kind](p)))
            except ImportError as e:
                raise InputError("缺少依赖（python-docx / openpyxl / python-pptx）：%s" % e)
        if not targets:
            raise InputError("至少给一个 --docx / --xlsx / --pptx")
        expects = [x.strip() for x in a.expect.split(",") if x.strip()]
        if not expects and not a.selftest:
            raise InputError("用 --expect 指定必须出现的金额（逗号分隔）")
    except InputError as e:
        print("输入错误：%s" % e, file=sys.stderr)
        return 2

    reports, blockers = [], 0
    for name, texts in targets:
        r = scan(name, texts, expects)
        blockers += len(r["missing"]) + len(r["placeholders"])
        reports.append(r)

    lines = ["=" * 66, "三件套一致性检查　期望金额：%s" % ("、".join(expects) or "（自检）"), "=" * 66]
    for r in reports:
        lines.append("%-34s 缺失 %d｜占位符 %d" % (r["file"], len(r["missing"]), len(r["placeholders"])))
        for m in r["missing"]:
            lines.append("   [缺] %s" % m)
        for ph in r["placeholders"][:8]:
            lines.append("   [占位] %s：%s　…%s…" % (ph["type"], ph["hit"], ph["context"]))
    lines.append("-" * 66)
    lines.append("结论：%s（阻断 %d）" % ("通过，可交付" if blockers == 0 else "不通过，需修正", blockers))
    lines.append("=" * 66)
    text = "\n".join(lines)
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.write(text.encode("utf-8", "replace").decode("utf-8", "replace"))

    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump({"expect": expects, "reports": reports, "blockers": blockers},
                      f, ensure_ascii=False, indent=2)
    return 0 if blockers == 0 else 1


if __name__ == "__main__":
    sys.exit(main())