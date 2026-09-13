# -*- coding: utf-8 -*-
"""Fourteenth pass: v18 -> v19. Apply the same light-blue "web" table style
(blue header row, alternating pale-blue/white body rows) to EVERY table in
the document, not just Tabela 8."""
from pathlib import Path

import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

SRC = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v18.docx")
DST = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v19.docx")

d = docx.Document(SRC)

HEADER_BLUE = "BDD7EE"
ROW_ALT = "EAF1FB"
ROW_WHITE = "FFFFFF"


def shade_cell(cell, hex_color: str):
    tcPr = cell._tc.get_or_add_tcPr()
    for existing in tcPr.findall(qn("w:shd")):
        tcPr.remove(existing)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


for ti, t in enumerate(d.tables):
    for c in t.rows[0].cells:
        shade_cell(c, HEADER_BLUE)
        for p in c.paragraphs:
            for r in p.runs:
                r.bold = True
    for ridx in range(1, len(t.rows)):
        color = ROW_ALT if ridx % 2 == 1 else ROW_WHITE
        for c in t.rows[ridx].cells:
            shade_cell(c, color)
    print(f"styled table {ti} ({len(t.rows)} rows)")

d.save(DST)
print("Saved ->", DST)
