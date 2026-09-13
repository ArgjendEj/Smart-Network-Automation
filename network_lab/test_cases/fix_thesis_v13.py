# -*- coding: utf-8 -*-
"""Thirteenth pass: v17 -> v18.

User feedback:
1) Tabela 8 (koha e konfigurimit) names departments only in the first row
   ("2 departamente (Sales, IT)") while the other three rows just say "N
   departamente" -- drop the names for consistency.
2) Style Tabela 8 with a light-blue, "web-like" look (blue header row,
   alternating light-blue/white body rows) instead of the plain black/white
   grid used elsewhere.
"""
from pathlib import Path

import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

SRC = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v17.docx")
DST = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v18.docx")

d = docx.Document(SRC)

# Tabela 8 = d.tables[8] (0-based), confirmed by header row content.
t = d.tables[8]
assert t.rows[0].cells[1].text.strip() == "Manual"

# ---- 1. drop the department names from the first data row
cell = t.rows[1].cells[0]
for p in cell.paragraphs:
    for r in list(p.runs):
        r._element.getparent().remove(r._element)
cell.paragraphs[0].add_run("2 departamente")


def shade_cell(cell, hex_color: str):
    tcPr = cell._tc.get_or_add_tcPr()
    for existing in tcPr.findall(qn("w:shd")):
        tcPr.remove(existing)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


HEADER_BLUE = "BDD7EE"   # light blue
ROW_ALT = "EAF1FB"       # very pale blue
ROW_WHITE = "FFFFFF"

# ---- 2. header row: solid light blue + bold white-ish dark blue text for contrast
for c in t.rows[0].cells:
    shade_cell(c, HEADER_BLUE)
    for p in c.paragraphs:
        for r in p.runs:
            r.bold = True

# ---- 3. body rows: alternate pale blue / white
for ridx in range(1, len(t.rows)):
    color = ROW_ALT if ridx % 2 == 1 else ROW_WHITE
    for c in t.rows[ridx].cells:
        shade_cell(c, color)

d.save(DST)
print("Saved ->", DST)
