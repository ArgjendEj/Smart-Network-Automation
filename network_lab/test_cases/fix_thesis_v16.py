# -*- coding: utf-8 -*-
"""Sixteenth pass: v20 -> v21.

User shared a screenshot of a nicely formatted Table of Contents (bold
chapter-level entries, indented sub-levels, dot leaders to the page
number) and asked for PËRMBAJTJA to look the same way.

The dot-leader tabs were already correctly configured; what was missing
was: (1) bold text for top-level chapter entries ("1  HYRJE", "2  ...",
etc.), and (2) progressive left indentation for "X.Y" (level 2) and
"X.Y.Z" (level 3) sub-entries. Front-matter entries with no number
(ABSTRAKT, LISTA E FIGURAVE, REFERENCAT, ...) stay flush-left, unbolded.
"""
import re
from pathlib import Path

import docx
from docx.shared import Inches

SRC = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v20.docx")
DST = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v21.docx")

d = docx.Document(SRC)
P = d.paragraphs

i_start = next(i for i, p in enumerate(P) if p.text.strip() == "P\u00cbRMBAJTJA")
i_end = next(i for i, p in enumerate(P) if p.text.strip() == "LISTA E FIGURAVE")

NUM_RE = re.compile(r"^(\d+(?:\.\d+)*)\s")

changed = 0
for i in range(i_start + 1, i_end):
    p = P[i]
    text = p.text.strip()
    if not text:
        continue
    m = NUM_RE.match(text)
    if m:
        depth = m.group(1).count(".")  # 0 = "1", 1 = "1.1", 2 = "1.1.1"
    else:
        depth = -1  # front-matter, no number

    if depth <= 0:
        p.paragraph_format.left_indent = None
    elif depth == 1:
        p.paragraph_format.left_indent = Inches(0.28)
    else:
        p.paragraph_format.left_indent = Inches(0.56)

    bold = (depth == 0)
    for r in p.runs:
        r.bold = bold
    changed += 1

print(f"restyled {changed} TOC entries")
d.save(DST)
print("Saved ->", DST)
