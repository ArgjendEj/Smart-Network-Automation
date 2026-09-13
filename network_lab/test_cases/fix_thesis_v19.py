# -*- coding: utf-8 -*-
"""Nineteenth pass: v23 -> v24.

User pointed out the screenshot shows a small floating toolbar above the
TOC ("Update Table..." pill button) when the cursor is inside it. That
overlay is Word's native UI for a TOC inserted from the References >
Table of Contents GALLERY, which wraps the field in a content control
(<w:sdt> with docPartGallery="Table of Contents"). My previous pass
inserted a bare field (begin/instrText/separate/end) without that
wrapper, so Word doesn't show the gallery toolbar for it, even though the
field itself works fine via right-click "Update Field".

This pass finds the true outer TOC field's start/end paragraphs (using
proper fldChar begin/end stack matching, since the field also contains
many NESTED PAGEREF fields for each entry's page number -- naive
first-end-found matching grabs an inner field's end instead) and wraps
that whole paragraph range in the same <w:sdt> content-control structure
Word's own gallery command produces.
"""
from pathlib import Path

import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

SRC = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v23.docx")
DST = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v24.docx")

d = docx.Document(SRC)
body = d.element.body


def owning_para(el):
    node = el
    while node is not None and node.tag != qn("w:p"):
        node = node.getparent()
    return node


stack = []
toc_begin_el = None
toc_end_el = None
for el in body.iter():
    tag = el.tag.split("}")[-1]
    if tag == "fldChar":
        typ = el.get(qn("w:fldCharType"))
        if typ == "begin":
            stack.append(el)
        elif typ == "end":
            if stack:
                begin_el = stack.pop()
                if begin_el is toc_begin_el and toc_end_el is None:
                    toc_end_el = el
    elif tag == "instrText":
        if el.text and "TOC \\o" in el.text and toc_begin_el is None and stack:
            toc_begin_el = stack[-1]

assert toc_begin_el is not None and toc_end_el is not None, "TOC field not found"

begin_p = owning_para(toc_begin_el)
end_p = owning_para(toc_end_el)

P = d.paragraphs
begin_i = next(i for i, p in enumerate(P) if p._p is begin_p)
end_i = next(i for i, p in enumerate(P) if p._p is end_p)
print(f"wrapping paragraphs {begin_i}..{end_i} in a Table-of-Contents content control")

field_paras = [P[j]._p for j in range(begin_i, end_i + 1)]

sdt = OxmlElement("w:sdt")
sdtPr = OxmlElement("w:sdtPr")
docPartObj = OxmlElement("w:docPartObj")
gallery = OxmlElement("w:docPartGallery")
gallery.set(qn("w:val"), "Table of Contents")
unique = OxmlElement("w:docPartUnique")
docPartObj.append(gallery)
docPartObj.append(unique)
sdtPr.append(docPartObj)
sdt.append(sdtPr)
sdt.append(OxmlElement("w:sdtEndPr"))
sdtContent = OxmlElement("w:sdtContent")
sdt.append(sdtContent)

parent = field_paras[0].getparent()
parent.insert(list(parent).index(field_paras[0]), sdt)
for fp in field_paras:
    parent.remove(fp)
    sdtContent.append(fp)

d.save(DST)
print("Saved ->", DST)
