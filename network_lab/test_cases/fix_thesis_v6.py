# -*- coding: utf-8 -*-
"""Sixth pass: v8 -> v9 (final). One closing synthesis paragraph."""
from pathlib import Path

import docx
from docx.oxml import OxmlElement
from docx.text.paragraph import Paragraph

SRC = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v8.docx")
DST = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v9.docx")

d = docx.Document(SRC)
P = d.paragraphs


def insert_para_after(ref: Paragraph, text="") -> Paragraph:
    new_p = OxmlElement("w:p")
    ref._p.addnext(new_p)
    new_para = Paragraph(new_p, ref._parent)
    new_para.add_run(text)
    return new_para


def find(substr: str) -> int:
    for i, p in enumerate(P):
        if substr in p.text:
            return i
    raise ValueError(f"not found: {substr!r}")


i = find("P\u00ebrfundimi m\u00eb i gjer\u00eb \u00ebsht\u00eb se automatizimi")
insert_para_after(P[i],
    "Tri lloje provash e mbështetën këtë punim: rezultatet sasiore të matura "
    "drejtpërdrejt nga pipeline-i real (Kapitulli 6), kodi burimor i cituar "
    "fjalë për fjalë nga vetë platforma (Kodi 1–6) dhe pamjet e ekranit të "
    "kapura automatikisht nga aplikacioni në ekzekutim (Figura 3–10, seksioni "
    "4.5). Kjo tri-shtresëzim provash — numra, kod dhe ndërfaqe — e forcon "
    "pretendimin qendror: platforma nuk është një demonstrim konceptual, por "
    "një sistem funksional që administron një topologji prej 22 pajisjesh, e "
    "kalon një suite prej 32 testesh automatike dhe e prodhon konfigurimin e "
    "vet Cisco IOS në më pak se një sekondë për pajisje.")

d.save(DST)
print("Saved ->", DST)
