#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""deliverable_qc.py —— 交付物排版与结构体检

查四类"人眼会漏、客户一眼看出"的问题：
    1. docx 目录域是否已更新（未更新会显示"错误！未找到目录项"）
    2. docx 末尾是否有空白页 / 连续空段
    3. docx 表格是否跨页（需 --pdf，依赖 pymupdf；无 PDF 时跳过并提示）
    4. pptx 形状是否越出页面边界（文字/表格被裁掉的主因）

用法：
    python deliverable_qc.py --docx 方案.docx --pdf 方案.pdf --pptx 汇报.pptx [--json out.json]
    python deliverable_qc.py --docx 方案.docx            # 只做不需要 PDF 的检查

退出码：0 通过｜1 有问题｜2 输入错误
"""
import argparse, json, os, sys


class InputError(Exception):
    pass


def qc_docx_structure(path):
    from docx import Document
    from docx.oxml.ns import qn
    out = {"file": os.path.basename(path), "toc": None, "empty_tail": 0, "note": []}
    d = Document(path)

    # 1. 目录域：找 w:instrText 里含 TOC 的域，并看有没有缓存文本
    instr = d.element.body.findall('.//' + qn('w:instrText'))
    has_toc = any("TOC" in (e.text or "") for e in instr)
    # 缓存文本：TOC 域生成的每条目录项都带一个 PAGEREF 域；
    # 样式名在不同语言版 Word 里是 "TOC 1" 或 "目录 1"，故两种都认
    cached = sum(1 for e in instr if "PAGEREF" in (e.text or ""))
    if cached == 0:
        cached = sum(1 for p in d.paragraphs
                     if (p.style.name or "").startswith(("TOC", "目录")))
    if has_toc and cached == 0:
        out["toc"] = "未更新"
        out["note"].append("目录域存在但没有缓存文本：交付前在 Word 里更新域（Ctrl+A → F9）")
    elif has_toc:
        out["toc"] = "已更新（%d 行）" % cached
    else:
        out["toc"] = "无目录域"

    # 2. 末尾空段
    tail = 0
    for p in reversed(d.paragraphs):
        if p.text.strip():
            break
        tail += 1
    out["empty_tail"] = tail
    if tail > 2:
        out["note"].append("文档末尾有 %d 个连续空段，可能形成空白页" % tail)
    return out


def qc_table_pages(docx_path, pdf_path):
    """caption 与末行是否同页（同页共现判定，避免全文搜索假命中）"""
    try:
        import pymupdf
    except ImportError:
        return {"skipped": "未安装 pymupdf，跳过表格跨页检查"}
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    import re

    doc = Document(docx_path)
    items = []
    for child in doc.element.body.iterchildren():
        if child.tag.endswith('}p'):
            items.append(("p", Paragraph(child, doc)))
        elif child.tag.endswith('}tbl'):
            items.append(("t", Table(child, doc)))

    def norm(s):
        return re.sub(r"\s+", "", s or "")

    pairs, cap = [], None
    for kind, obj in items:
        if kind == "p":
            t = obj.text.strip()
            if re.match(r"^表\s*[0-9A-Z]", t):
                cap = t
        else:
            if cap and len(obj.rows) > 1:
                pairs.append((cap[:30], norm("".join(c.text for c in obj.rows[-1].cells)),
                              len(obj.rows) - 1))
            cap = None

    pdf = pymupdf.open(pdf_path)
    pages = [norm(pdf[i].get_text()) for i in range(pdf.page_count)]
    split, whole, miss = [], 0, 0
    for caption, tail, n in pairs:
        cf = norm(caption)
        cand = [i for i, t in enumerate(pages) if cf and cf in t]
        if not cand:
            miss += 1
            continue
        if any(tail and tail in pages[i] for i in cand):
            whole += 1
        else:
            split.append({"caption": caption, "rows": n, "page": cand[0] + 1})
    return {"tables": len(pairs), "whole": whole, "split": split, "unlocated": miss}


def qc_pptx_bounds(path):
    from pptx import Presentation
    prs = Presentation(path)
    W, H = prs.slide_width, prs.slide_height
    bad, total = [], 0
    for i, s in enumerate(prs.slides, 1):
        for sh in s.shapes:
            total += 1
            try:
                l, t, w, h = sh.left, sh.top, sh.width, sh.height
            except Exception:
                continue
            if l is None or t is None or w is None or h is None:
                continue
            over = (l + w > W + 9144) or (t + h > H + 9144) or l < -9144 or t < -9144
            if over:
                bad.append({"slide": i, "shape": (sh.name or "")[:24],
                            "right_cm": round((l + w) / 360000, 2), "page_cm": round(W / 360000, 2)})
    return {"shapes": total, "out_of_bounds": bad, "slide_cm": (round(W / 360000, 2), round(H / 360000, 2))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docx", default="")
    ap.add_argument("--pdf", default="")
    ap.add_argument("--pptx", default="")
    ap.add_argument("--json", default="")
    a = ap.parse_args()

    if not (a.docx or a.pptx):
        print("输入错误：至少给 --docx 或 --pptx", file=sys.stderr)
        return 2
    for p in (a.docx, a.pdf, a.pptx):
        if p and not os.path.exists(p):
            print("输入错误：文件不存在 %s" % p, file=sys.stderr)
            return 2

    report, problems = {}, 0
    if a.docx:
        try:
            report["docx"] = qc_docx_structure(a.docx)
            problems += len(report["docx"]["note"])
        except ImportError:
            print("输入错误：需要 python-docx", file=sys.stderr)
            return 2
        if a.pdf:
            report["tables"] = qc_table_pages(a.docx, a.pdf)
            problems += len(report["tables"].get("split", []))
        else:
            report["tables"] = {"skipped": "未提供 --pdf，跳过跨页检查"}
    if a.pptx:
        try:
            report["pptx"] = qc_pptx_bounds(a.pptx)
            problems += len(report["pptx"]["out_of_bounds"])
        except ImportError:
            print("输入错误：需要 python-pptx", file=sys.stderr)
            return 2

    L = ["=" * 70, "交付物体检", "-" * 70]
    if "docx" in report:
        d = report["docx"]
        L.append("docx　目录：%s｜末尾空段：%d" % (d["toc"], d["empty_tail"]))
        for n in d["note"]:
            L.append("   [问题] " + n)
    t = report.get("tables", {})
    if "skipped" in t:
        L.append("表格跨页：%s" % t["skipped"])
    elif t:
        L.append("表格　共 %d｜同页 %d｜跨页 %d｜未定位 %d"
                 % (t["tables"], t["whole"], len(t["split"]), t["unlocated"]))
        for s in t["split"]:
            L.append("   [跨页] %s（%d 行，起始第 %d 页）" % (s["caption"], s["rows"], s["page"]))
    if "pptx" in report:
        p = report["pptx"]
        L.append("pptx　形状 %d｜越界 %d｜页面 %.2f×%.2f cm"
                 % (p["shapes"], len(p["out_of_bounds"]), p["slide_cm"][0], p["slide_cm"][1]))
        for s in p["out_of_bounds"][:8]:
            L.append("   [越界] 第%d页 %s 右边界 %.2f > %.2f"
                     % (s["slide"], s["shape"], s["right_cm"], s["page_cm"]))
    L.append("-" * 70)
    L.append("结论：%s（问题 %d）" % ("通过" if problems == 0 else "需修正", problems))
    L.append("=" * 70)
    text = "\n".join(L)
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.write(text.encode("utf-8", "replace").decode("utf-8", "replace"))

    if a.json:
        report["problems"] = problems
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print("报告已写出：%s" % a.json)
    return 0 if problems == 0 else 1


if __name__ == "__main__":
    sys.exit(main())