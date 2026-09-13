# -*- coding: utf-8 -*-
"""Twelfth pass: v16 -> v17. Small transparency note in the Appendix
explaining that full per-device configs (beyond the excerpts cited in the
body) live in the repo -- recovers a bit of the page/word space lost when
the Kodi 7 / SW1-SW2 / Tabela 12 appendix block was removed per user
feedback, without reintroducing raw code."""
from pathlib import Path

import docx
from docx.oxml import OxmlElement
from docx.text.paragraph import Paragraph

SRC = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v16.docx")
DST = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v17.docx")

d = docx.Document(SRC)
P = d.paragraphs


def find(substr: str) -> int:
    for i, p in enumerate(P):
        if substr in p.text:
            return i
    raise ValueError(f"not found: {substr!r}")


def insert_para_after(ref: Paragraph, text="") -> Paragraph:
    new_p = OxmlElement("w:p")
    ref._p.addnext(new_p)
    new_para = Paragraph(new_p, ref._parent)
    new_para.add_run(text)
    return new_para


i = find("Suita e testeve automatike dhe udh\u00ebzuesi p\u00ebr ekzekutimin")
cur = insert_para_after(
    P[i],
    "Konfigurimet e plota, t\u00eb gjeneruara automatikisht p\u00ebr \u00e7do router dhe "
    "switch t\u00eb topologjis\u00eb demonstruese (jo vet\u00ebm fragmentet e cituara n\u00eb "
    "Kapitullin 5 dhe n\u00eb Figur\u00ebn 8), gjenden t\u00eb plota n\u00eb depo, t\u00eb ruajtura si "
    "dalje reale e skriptit t\u00eb gjenerimit \u2014 jo t\u00eb rishkruara me dor\u00eb p\u00ebr "
    "qëllime dokumentimi."
)
insert_para_after(
    cur,
    "Kjo qasje \u2014 citimi i fragmenteve m\u00eb t\u00eb r\u00ebnd\u00ebsishme n\u00eb tekst dhe l\u00ebnia "
    "e listimeve t\u00eb plota n\u00eb depo \u2014 u zgjodh me q\u00ebllim, p\u00ebr ta mbajtur trupin "
    "kryesor t\u00eb punimit t\u00eb lexueshëm pa e humbur riprodhueshm\u00ebrin\u00ebn: \u00e7do "
    "pretendim sasior i Kapitullit 6 mund t\u00eb verifikohet direkt kund\u00ebr "
    "skedar\u00ebve real\u00eb t\u00eb konfigurimit, jo vet\u00ebm kund\u00ebr fragmenteve t\u00eb cituara."
)

d.save(DST)
print("Saved ->", DST)
