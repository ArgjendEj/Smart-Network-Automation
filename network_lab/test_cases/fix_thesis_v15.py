# -*- coding: utf-8 -*-
"""Fifteenth pass: v19 -> v20.

User asked for all code exhibits (Kodi 1-6 + the Cisco IOS block under
Figura 8) to look like a real syntax-highlighted code editor (line numbers,
colored keywords/strings/comments), like the VS Code style screenshot they
shared, instead of plain black Consolas text.

Implementation: replace each plain-text code block with a 2-column,
border-light table (line-number gutter | syntax-highlighted code), using
pygments (PythonLexer / DjangoLexer for Jinja2, plus a small custom
highlighter for Cisco IOS, which pygments has no lexer for) with the
Visual Studio ("vs") light color scheme, tight single-line spacing, and a
very light gray card background -- matching a real editor's look.
"""
import re
from pathlib import Path

import docx
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

from pygments import lex
from pygments.lexers import PythonLexer, DjangoLexer
from pygments.styles import get_style_by_name

SRC = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v19.docx")
DST = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v20.docx")

d = docx.Document(SRC)
P = d.paragraphs

VSStyle = get_style_by_name("vs")
BG = "F7F7F7"        # code card background
GUTTER_BORDER = "D9D9D9"
BORDER = "D0D0D0"
LINE_NO_COLOR = "9A9A9A"
CODE_FONT = "Consolas"
CODE_SIZE = Pt(9)
NUM_SIZE = Pt(8.5)


def find(substr: str) -> int:
    for i, p in enumerate(P):
        if substr in p.text:
            return i
    raise ValueError(f"not found: {substr!r}")


def find_last(substr: str) -> int:
    hits = [i for i, p in enumerate(P) if substr in p.text]
    if not hits:
        raise ValueError(f"not found: {substr!r}")
    return hits[-1]


def remove_para(para: Paragraph):
    para._p.getparent().remove(para._p)


def tight(para: Paragraph):
    pf = para.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    pf.line_spacing = 1.0


def token_style(ttype):
    s = VSStyle.style_for_token(ttype)
    color = s["color"] or "000000"
    return color, bool(s["bold"]), bool(s["italic"])


CISCO_KEYWORDS = {
    "hostname", "no", "ip", "domain-lookup", "domain-name", "service",
    "password-encryption", "routing", "dhcp", "excluded-address", "pool",
    "network", "default-router", "dns-server", "interface", "description",
    "address", "shutdown", "router", "ospf", "bgp", "router-id",
    "passive-interface", "area", "banner", "motd", "line", "con",
    "logging", "synchronous", "end", "vlan", "name", "spanning-tree",
    "mode", "pvst", "switchport", "access", "range", "portfast", "nat",
    "inside", "outside", "access-list", "permit", "source", "list",
    "overload", "neighbor", "remote-as", "log-neighbor-changes",
}
IP_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


def cisco_tokens(line: str):
    """Yield (text, hexcolor_or_None, bold) chunks for one Cisco IOS line."""
    stripped = line.strip()
    if stripped.startswith("!"):
        yield line, "2E7D32", False
        return
    if "###" in line:
        yield line, "2E7D32", False
        return
    # split but keep the whitespace so leading indentation is preserved
    parts = re.split(r"(\s+)", line)
    for part in parts:
        if part == "" or part.isspace():
            yield part, None, False
        elif part.lower() in CISCO_KEYWORDS:
            yield part, "0000CC", True
        elif IP_RE.match(part):
            yield part, "B5860B", False
        elif re.match(r"^\d+$", part):
            yield part, "B5860B", False
        else:
            yield part, "000000", False


def shade_cell(cell, hex_color: str):
    tcPr = cell._tc.get_or_add_tcPr()
    for existing in tcPr.findall(qn("w:shd")):
        tcPr.remove(existing)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


def set_cell_border(cell, **kwargs):
    """kwargs like top={'val':'single','sz':4,'color':'D0D0D0'}"""
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = tcPr.find(qn("w:tcBorders"))
    if tcBorders is None:
        tcBorders = OxmlElement("w:tcBorders")
        tcPr.append(tcBorders)
    for edge, spec in kwargs.items():
        el = tcBorders.find(qn(f"w:{edge}"))
        if el is None:
            el = OxmlElement(f"w:{edge}")
            tcBorders.append(el)
        for k, v in spec.items():
            el.set(qn(f"w:{k}"), str(v))


def set_cell_margins(cell, top=40, bottom=40, left=80, right=80):
    tcPr = cell._tc.get_or_add_tcPr()
    mar = OxmlElement("w:tcMar")
    for edge, val in (("top", top), ("bottom", bottom), ("left", left), ("right", right)):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:w"), str(val))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    tcPr.append(mar)


NUM_COL_IN = 0.42
CODE_COL_IN = 6.268 - NUM_COL_IN


def build_code_table(anchor: Paragraph, code_lines, lexer):
    n = len(code_lines)
    tbl = d.add_table(rows=n, cols=2)
    tbl.autofit = False
    tblPr = tbl._tbl.tblPr
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tblPr.append(layout)
    tblW = OxmlElement("w:tblW")
    tblW.set(qn("w:type"), "dxa")
    tblW.set(qn("w:w"), str(int(Inches(6.268) / 635)))
    tblPr.append(tblW)
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:color"), BORDER)
        el.set(qn("w:sz"), "4")
        borders.append(el)
    for edge in ("insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "nil")
        borders.append(el)
    tblPr.append(borders)

    tbl.columns[0].width = Inches(NUM_COL_IN)
    tbl.columns[1].width = Inches(CODE_COL_IN)
    for row in tbl.rows:
        row.cells[0].width = Inches(NUM_COL_IN)
        row.cells[1].width = Inches(CODE_COL_IN)

    for i, line in enumerate(code_lines):
        numcell, codecell = tbl.rows[i].cells
        shade_cell(numcell, BG)
        shade_cell(codecell, BG)
        set_cell_border(numcell, right={"val": "single", "sz": 4, "color": GUTTER_BORDER})
        set_cell_margins(numcell, left=40, right=60)
        set_cell_margins(codecell, left=100, right=60)

        p = numcell.paragraphs[0]
        tight(p)
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        r = p.add_run(str(i + 1))
        r.font.name = CODE_FONT
        r.font.size = NUM_SIZE
        r.font.color.rgb = RGBColor.from_string(LINE_NO_COLOR)

        p2 = codecell.paragraphs[0]
        tight(p2)
        if lexer is None:
            chunks = list(cisco_tokens(line))
        else:
            src = (line if line else " ") + "\n"
            chunks = []
            for ttype, value in lex(src, lexer):
                value = value.replace("\n", "")
                if value == "":
                    continue
                color, bold, italic = token_style(ttype)
                chunks.append((value, color, bold))
        if not chunks:
            p2.add_run(" ")
        for item in chunks:
            text = item[0]
            color = item[1]
            bold = item[2] if len(item) > 2 else False
            if text == "":
                continue
            run = p2.add_run(text)
            run.font.name = CODE_FONT
            run.font.size = CODE_SIZE
            if color:
                run.font.color.rgb = RGBColor.from_string(color)
            if bold:
                run.bold = True

    anchor._p.addnext(tbl._tbl)
    marker_p = OxmlElement("w:p")
    tbl._tbl.addnext(marker_p)
    return Paragraph(marker_p, anchor._parent)


NUM_PREFIX_RE = re.compile(r"^\s*\d+\s\s?")


def strip_num_prefix(text: str) -> str:
    return NUM_PREFIX_RE.sub("", text, count=1)


# ---------------------------------------------------------------- blocks
py_lexer = PythonLexer()
jinja_lexer = DjangoLexer()

blocks = [
    ("Kodi 1 e paraqet funksionin q\u00eb e zbaton skem\u00ebn deterministike",
     "Kodi 1. Nxjerrja deterministike e identifikuesit t\u00eb VLAN-it nga subneti.",
     py_lexer, False),
    ("Kodi 2 e paraqet logjik\u00ebn baz\u00eb t\u00eb llogaritjes s\u00eb n\u00ebnrrjetit",
     "Kodi 2. Llogaritja e n\u00ebnrrjetit dhe nxjerrja e adres\u00ebs s\u00eb par\u00eb t\u00eb lir\u00eb.",
     py_lexer, True),
    ("Kodi 3 e paraqet logjik\u00ebn e caktimit t\u00eb adresave",
     "Kodi 3. Caktimi automatik i adresave p\u00ebr nj\u00eb lidhje router-me-router.",
     py_lexer, True),
    ("Kodi 4 e paraqet nj\u00eb fragment t\u00eb shabllonit q\u00eb i gjeneron interface-t",
     "Kodi 4. Fragment i shabllonit Jinja2 p\u00ebr gjenerimin e interface-ve t\u00eb routerit.",
     jinja_lexer, True),
    ("Konfigurimi i m\u00ebposht\u00ebm \u00ebsht\u00eb dalja reale e platform\u00ebs",
     "Figura 8. Konfigurimi i gjeneruar Cisco IOS p\u00ebr nj\u00eb router.",
     None, False),
    ("Kodi 5 e paraqet funksionin qendror t\u00eb rrug\u00ebs Netmiko",
     "Kodi 5. D\u00ebrgimi i konfigurimit te pajisja reale p\u00ebrmes Netmiko.",
     py_lexer, False),
    ("Kodi 6 e paraqet funksionin e brendsh\u00ebm resolve()",
     "Kodi 6. Rezolucioni i nj\u00eb adrese n\u00eb modalitetin e verifikimit t\u00eb projektimit.",
     py_lexer, False),
]

for intro_text, caption_text, lexer, has_prefix in blocks:
    i_intro = find(intro_text)
    i_caption = find_last(caption_text)
    code_paras = [P[j] for j in range(i_intro + 1, i_caption)]
    code_lines = [pp.text for pp in code_paras]
    if has_prefix:
        code_lines = [strip_num_prefix(t) for t in code_lines]
    anchor = P[i_intro]
    for pp in code_paras:
        remove_para(pp)
    build_code_table(anchor, code_lines, lexer)
    print(f"rebuilt: {caption_text[:50]} ({len(code_lines)} lines, lexer={lexer.__class__.__name__ if lexer else 'cisco'})")

d.save(DST)
print("Saved ->", DST)
