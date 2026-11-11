# -*- coding: utf-8 -*-
"""Word 排版工具：中文方案书通用样式（正文宋体五号、标题微软雅黑、页眉页脚、表格、图注）"""
import os
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

NAVY = RGBColor(0x22, 0x31, 0x5B)
BLUE = RGBColor(0x3C, 0x6E, 0x9E)
GREEN = RGBColor(0x2E, 0x7D, 0x5B)
SAND = RGBColor(0xC9, 0x8A, 0x3C)
GREY = RGBColor(0x59, 0x59, 0x59)
LGREY = RGBColor(0x8A, 0x93, 0xA0)
DARK = RGBColor(0x1B, 0x21, 0x30)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
CONTENT_W = 15.5

DOC = None


def set_run(run, size=10.5, bold=False, color=None, name_cn="宋体", name_en="Times New Roman", italic=False):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.name = name_en
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.append(rFonts)
    rFonts.set(qn("w:ascii"), name_en)
    rFonts.set(qn("w:hAnsi"), name_en)
    rFonts.set(qn("w:eastAsia"), name_cn)
    rFonts.set(qn("w:cs"), name_en)
    if color is not None:
        run.font.color.rgb = color


def shade(cell, hex_fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tcPr.append(shd)


def vcenter(cell):
    tcPr = cell._tc.get_or_add_tcPr()
    el = OxmlElement("w:vAlign")
    el.set(qn("w:val"), "center")
    tcPr.append(el)


def cell_margins(t, top=40, bottom=40, left=80, right=80):
    tblPr = t._tbl.tblPr
    mar = OxmlElement("w:tblCellMar")
    for side, val in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:w"), str(val))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    tblPr.append(mar)


def repeat_header(row):
    trPr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    trPr.append(el)


def no_split(row):
    trPr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:cantSplit")
    el.set(qn("w:val"), "true")
    trPr.append(el)


def add_field(para, instr, placeholder="1"):
    run = para.add_run()
    f1 = OxmlElement("w:fldChar"); f1.set(qn("w:fldCharType"), "begin")
    it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve"); it.text = instr
    f2 = OxmlElement("w:fldChar"); f2.set(qn("w:fldCharType"), "separate")
    tt = OxmlElement("w:t"); tt.text = placeholder
    f3 = OxmlElement("w:fldChar"); f3.set(qn("w:fldCharType"), "end")
    for el in (f1, it, f2, tt, f3):
        run._r.append(el)
    return run


def hrule(paragraph, color="C9CFD8", size=6):
    pPr = paragraph._p.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), str(size))
    bottom.set(qn("w:space"), "4")
    bottom.set(qn("w:color"), color)
    pbdr.append(bottom)
    pPr.append(pbdr)


def init_docx(header_text, footer_left=""):
    global DOC
    doc = Document()
    DOC = doc
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    sec.top_margin, sec.bottom_margin = Cm(2.4), Cm(2.2)
    sec.left_margin, sec.right_margin = Cm(2.75), Cm(2.75)
    sec.header_distance, sec.footer_distance = Cm(1.4), Cm(1.3)

    st = doc.styles["Normal"]
    st.font.size = Pt(10.5)
    st.font.name = "Times New Roman"
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    pf = st.paragraph_format
    pf.line_spacing = 1.45
    pf.space_after = Pt(4)
    pf.space_before = Pt(0)

    for name, size, color, before, after in (
            ("Heading 1", 16, NAVY, 20, 10),
            ("Heading 2", 13, NAVY, 14, 6),
            ("Heading 3", 11, GREEN, 10, 4)):
        s = doc.styles[name]
        s.font.size = Pt(size)
        s.font.bold = True
        s.font.color.rgb = color
        s.font.name = "微软雅黑"
        for k in ("w:eastAsia", "w:ascii", "w:hAnsi"):
            s.element.rPr.rFonts.set(qn(k), "微软雅黑")
        s.paragraph_format.space_before = Pt(before)
        s.paragraph_format.space_after = Pt(after)
        s.paragraph_format.keep_with_next = True
        s.paragraph_format.line_spacing = 1.2

    sec.different_first_page_header_footer = True
    hdr = sec.header.paragraphs[0]
    hdr.alignment = WD_ALIGN_PARAGRAPH.LEFT
    r = hdr.add_run(header_text)
    set_run(r, 8.5, False, GREY, "微软雅黑")
    hrule(hdr)

    ftr = sec.footer.paragraphs[0]
    ftr.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = ftr.add_run("第 ")
    set_run(r, 9, False, GREY, "微软雅黑")
    add_field(ftr, " PAGE ", "1")
    r = ftr.add_run(" 页　共 ")
    set_run(r, 9, False, GREY, "微软雅黑")
    add_field(ftr, " NUMPAGES ", "1")
    r = ftr.add_run(" 页")
    for run in ftr.runs:
        set_run(run, 9, False, GREY, "微软雅黑")
    return doc


def para(text, indent=True, size=10.5, bold=False, color=None, after=4, before=0,
         align=WD_ALIGN_PARAGRAPH.JUSTIFY, spacing=1.45):
    p = DOC.add_paragraph()
    p.paragraph_format.first_line_indent = Pt(21) if indent else None
    p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.line_spacing = spacing
    p.alignment = align
    r = p.add_run(text)
    set_run(r, size, bold, color, "宋体")
    return p


def bullets(items, size=10.5, color=DARK):
    for it in items:
        p = DOC.add_paragraph()
        p.paragraph_format.left_indent = Pt(21)
        p.paragraph_format.first_line_indent = Pt(-10.5)
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.line_spacing = 1.4
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        r = p.add_run("▪ ")
        set_run(r, size, False, BLUE, "宋体")
        r = p.add_run(it)
        set_run(r, size, False, color, "宋体")


def note(text, label="说明："):
    p = DOC.add_paragraph()
    p.paragraph_format.left_indent = Pt(10)
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.line_spacing = 1.35
    pPr = p._p.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr")
    left = OxmlElement("w:left")
    left.set(qn("w:val"), "single"); left.set(qn("w:sz"), "18")
    left.set(qn("w:space"), "8"); left.set(qn("w:color"), "C98A3C")
    pbdr.append(left)
    pPr.append(pbdr)
    r = p.add_run(label)
    set_run(r, 9, True, SAND, "微软雅黑")
    r = p.add_run(text)
    set_run(r, 9, False, GREY, "宋体")


def caption(text, above=True):
    p = DOC.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(8 if above else 3)
    p.paragraph_format.space_after = Pt(3 if above else 10)
    p.paragraph_format.keep_with_next = above
    r = p.add_run(text)
    set_run(r, 9, True, NAVY, "微软雅黑")


def table(spec):
    headers, rows = spec["headers"], spec["rows"]
    widths = spec.get("widths") or [CONTENT_W / len(headers)] * len(headers)
    s = sum(widths)
    widths = [w * CONTENT_W / s for w in widths]
    fs = spec.get("fs", 9)
    aligns = spec.get("align") or ["l"] * len(headers)
    if spec.get("caption"):
        caption(spec["caption"], above=True)
    t = DOC.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    cell_margins(t)
    amap = {"l": WD_ALIGN_PARAGRAPH.LEFT, "c": WD_ALIGN_PARAGRAPH.CENTER, "r": WD_ALIGN_PARAGRAPH.RIGHT}
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]
        c.width = Cm(widths[i])
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.line_spacing = 1.1
        r = p.add_run(h)
        set_run(r, fs, True, WHITE, "微软雅黑")
        shade(c, "22315B")
        vcenter(c)
    repeat_header(t.rows[0])
    no_split(t.rows[0])
    for ri, row in enumerate(rows):
        cells = t.add_row().cells
        for i, v in enumerate(row):
            c = cells[i]
            c.width = Cm(widths[i])
            p = c.paragraphs[0]
            p.alignment = amap[aligns[i]]
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.line_spacing = 1.15
            r = p.add_run(str(v))
            bold = isinstance(v, str) and v.startswith("合计")
            set_run(r, fs, bold, DARK, "宋体")
            if ri % 2 == 1:
                shade(c, "F4F6F9")
            vcenter(c)
    keep_rows_together(t, spec.get("keep_rows", 13))
    sp = DOC.add_paragraph()
    sp.paragraph_format.space_after = Pt(2)
    sp.paragraph_format.line_spacing = 0.6
    return t



def keep_rows_together(t, max_rows=13):
    """行不跨页拆分；行数不多时把整表保持在一页内。

    Word 的行为：对除末行外所有段落设 keepNext，形成一条"链"；
    当链能放下一页时整表被推到下一页，放不下时自然断开（不会溢出）。
    """
    rows = t.rows
    for row in rows:
        no_split(row)
    if len(rows) - 1 <= max_rows:
        for row in rows[:-1]:
            for cell in row.cells:
                for p in cell.paragraphs:
                    p.paragraph_format.keep_with_next = True

def figure(spec):
    p = DOC.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(spec["path"], width=Cm(spec.get("width", 15.0)))
    caption(spec["caption"], above=False)


def render_blocks(blocks):
    for kind, payload in blocks:
        if kind == "p":
            para(payload)
        elif kind == "b":
            bullets(payload)
        elif kind == "t":
            table(payload)
        elif kind == "f":
            figure(payload)
        elif kind == "n":
            note(payload)


def h1(num, title, intro=None):
    h = DOC.add_heading(f"{num}　{title}", level=1)
    h.paragraph_format.space_before = Pt(6)
    for run in h.runs:
        set_run(run, 16, True, NAVY, "微软雅黑")
    hrule(h)
    if intro:
        p = DOC.add_paragraph()
        p.paragraph_format.space_after = Pt(10)
        p.paragraph_format.line_spacing = 1.4
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        r = p.add_run(intro)
        set_run(r, 10, False, GREY, "楷体")
    return h


def h2(num, title):
    h = DOC.add_heading(f"{num}　{title}", level=2)
    for run in h.runs:
        set_run(run, 13, True, NAVY, "微软雅黑")
    return h


def h2g(num, title):
    h = DOC.add_heading(f"{num}　{title}", level=2)
    for run in h.runs:
        set_run(run, 13, True, GREEN, "微软雅黑")
    return h


def page_break():
    p = DOC.add_paragraph()
    p.paragraph_format.space_after = Pt(0)
    p.add_run().add_break(WD_BREAK.PAGE)