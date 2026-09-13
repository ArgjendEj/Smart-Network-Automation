# -*- coding: utf-8 -*-
"""Eighteenth pass: v22 -> v23.

The real TOC field (inserted in the previous pass, then computed via Word)
copies DIRECT character formatting from each source heading's runs. Since
every Heading 2 / Heading 3 body paragraph in this document has direct
bold=True on its run (so the heading itself looks bold in the body text --
desirable, left untouched), that bold also got copied into the "toc 2" /
"toc 3" TOC entries, making sub-sections bold too. Only "toc 1" (numbered
chapters + REFERENCAT/APPENDIX) should be bold, matching the reference
screenshot. This pass force-clears bold specifically on the "toc 2" /
"toc 3" paragraphs' runs (including runs nested inside w:hyperlink, which
python-docx's paragraph.runs does not see).
"""
from pathlib import Path

import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

SRC = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v22.docx")
DST = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v23.docx")

d = docx.Document(SRC)

count = 0
for p in d.paragraphs:
    if p.style is not None and p.style.name in ("toc 2", "toc 3"):
        for r in p._p.findall(".//" + qn("w:r")):
            rPr = r.find(qn("w:rPr"))
            if rPr is None:
                rPr = OxmlElement("w:rPr")
                r.insert(0, rPr)
            b = rPr.find(qn("w:b"))
            if b is None:
                b = OxmlElement("w:b")
                rPr.append(b)
            b.set(qn("w:val"), "0")
        count += 1

print(f"cleared bold on {count} sub-level TOC entries")
d.save(DST)
print("Saved ->", DST)
