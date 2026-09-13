# -*- coding: utf-8 -*-
"""Seventeenth pass: v21 -> v22 (prep step, before a Word COM field-update).

User specifically asked for the real Word TOC MECHANISM (the "Update
Table" field, like the gray-shaded auto-generated TOC in the reference
screenshot) rather than a manually typed list -- which also happens to fix
a real staleness bug: the manual list was missing the 7.1.2-7.1.4
sub-headings that already exist in the body as real Heading 3 paragraphs.

This script:
1. Makes the remaining un-styled front-matter section titles (ABSTRAKT,
   MIRËNJOHJE/FALËNDERIME, LISTA E FIGURAVE, LISTA E TABELAVE, FJALORI I
   TERMAVE) use "Heading 1" like REFERENCAT/APPENDIX already do, and
   forces their run(s) to bold=False so they read as plain (not bold) in
   both the body and the generated TOC -- matching the numbered chapters
   (which already carry direct bold=True on their runs) being bold while
   these are not, exactly like the reference screenshot.
2. Deletes the old manually-typed PËRMBAJTJA list.
3. Inserts a real TOC field (`TOC \\o "1-3" \\h \\z \\u`) right after the
   "PËRMBAJTJA" title -- unpopulated; a follow-up Word COM step updates it
   to compute real page numbers/entries, exactly like clicking "Update
   Table" in Word.
"""
from pathlib import Path

import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

SRC = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v21.docx")
DST = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v22.docx")

d = docx.Document(SRC)
P = d.paragraphs


def remove_para(para: Paragraph):
    para._p.getparent().remove(para._p)


# ---- 1. front-matter titles -> Heading 1, forced non-bold runs
FRONT_TITLES = [
    "ABSTRAKT",
    "MIR\u00cbNJOHJE / FAL\u00cbNDERIME",
    "LISTA E FIGURAVE",
    "LISTA E TABELAVE",
    "FJALORI I TERMAVE",
]
heading1_style = next(s for s in d.styles if s.name == "Heading 1")

count = 0
for p in P:
    t = p.text.strip()
    if t in FRONT_TITLES and (p.style is None or p.style.name != "Heading 1"):
        p.style = heading1_style
        for r in p.runs:
            r.bold = False
        count += 1
print(f"restyled {count} front-matter titles to Heading 1 (non-bold)")

# ---- 2. delete the old manual PËRMBAJTJA list
P = d.paragraphs
i_title = next(i for i, p in enumerate(P) if p.text.strip() == "P\u00cbRMBAJTJA")
i_end = next(
    i for i in range(i_title + 1, len(P))
    if P[i].text.strip() == "LISTA E FIGURAVE" and P[i].style is not None and P[i].style.name == "Heading 1"
)
to_delete = [P[j] for j in range(i_title + 1, i_end)]
for p in to_delete:
    remove_para(p)
print(f"deleted {len(to_delete)} old manual TOC paragraphs")

# ---- 3. insert the real TOC field right after "PËRMBAJTJA"
P = d.paragraphs
anchor = P[i_title]

new_p = OxmlElement("w:p")
anchor._p.addnext(new_p)
toc_para = Paragraph(new_p, anchor._parent)

def add_run_el(parent_p, tag_builder):
    r = OxmlElement("w:r")
    parent_p._p.append(r)
    tag_builder(r)

r1 = OxmlElement("w:r")
fld_begin = OxmlElement("w:fldChar")
fld_begin.set(qn("w:fldCharType"), "begin")
fld_begin.set(qn("w:dirty"), "true")
r1.append(fld_begin)
toc_para._p.append(r1)

r2 = OxmlElement("w:r")
instr = OxmlElement("w:instrText")
instr.set(qn("xml:space"), "preserve")
instr.text = ' TOC \\o "1-3" \\h \\z \\u '
r2.append(instr)
toc_para._p.append(r2)

r3 = OxmlElement("w:r")
fld_sep = OxmlElement("w:fldChar")
fld_sep.set(qn("w:fldCharType"), "separate")
r3.append(fld_sep)
toc_para._p.append(r3)

r4 = OxmlElement("w:r")
t = OxmlElement("w:t")
t.text = "Kliko me të djathtën dhe zgjidh \u201eUpdate Field\u201c / \u201eUpdate Table\u201c."
r4.append(t)
toc_para._p.append(r4)

r5 = OxmlElement("w:r")
fld_end = OxmlElement("w:fldChar")
fld_end.set(qn("w:fldCharType"), "end")
r5.append(fld_end)
toc_para._p.append(r5)

print("inserted TOC field skeleton")

d.save(DST)
print("Saved ->", DST)
