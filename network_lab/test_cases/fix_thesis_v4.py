# -*- coding: utf-8 -*-
"""Fourth pass: v6 -> v7 (final). Two more grounded paragraphs: how the
figures were captured (methodological transparency) and a fifth future-work
direction, closing the remaining word-count gap."""
from pathlib import Path

import docx
from docx.oxml import OxmlElement
from docx.text.paragraph import Paragraph

SRC = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v6.docx")
DST = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v7.docx")

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


# --- 4.5: how the figures were captured (reproducibility note)
i = find("Kufizimi kryesor metodologjik \u00ebsht\u00eb se komponenti manual")
insert_para_after(P[i],
    "Figurat me pamje t\u00eb ekranit (Figura 3–5, 7, 9–10) janë marrë "
    "automatikisht, jo me dorë, përmes një skripti Playwright që hapet, "
    "kyçet me llogarinë e paracaktuar dhe navigon në secilën faqe të "
    "platformës reale duke përdorur shfletuesin e vetë sistemit "
    "(tests/take_screenshots.py). Ky proces është plotësisht i lexueshëm "
    "(read-only): asnjë pajisje, lidhje apo vlerë e bazës së të dhënave nuk "
    "ndryshohet gjatë kapjes së figurave, çka e mban topologjinë "
    "demonstruese identike përpara dhe pas dokumentimit.")

# --- 7.4: fifth future-work direction
i = find("Drejtimi i kat\u00ebrt \u00ebsht\u00eb vler\u00ebsimi empirik me p\u00ebrdorues real\u00eb")
insert_para_after(P[i],
    "Drejtimi i pest\u00eb është zgjerimi i kapjes automatike të pamjeve të "
    "ekranit (seksioni 4.5) në një suite testesh regresioni vizual: çdo "
    "ndryshim në ndërfaqe do të krahasohej automatikisht me pamjet e "
    "referencës, duke zbuluar dështime të paqëllimshme në dizajn përpara "
    "se ato të arrijnë te administratori.")

d.save(DST)
print("Saved ->", DST)
