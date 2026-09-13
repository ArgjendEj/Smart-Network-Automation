# -*- coding: utf-8 -*-
"""Eleventh pass: v14 -> v15.

User: remove this whole Appendix block entirely (Kodi 7 R2 fragment, the
SW1/SW2 VLAN-symmetry paragraph, and Tabela 12) — Getoar's reference thesis
does not have this kind of appendix code exhibit at all. Tabela 11 (device
inventory) stays; only Kodi 7 + the SW paragraph + Tabela 12 go.
"""
from pathlib import Path

import docx
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

SRC = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v14.docx")
DST = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v15.docx")

d = docx.Document(SRC)
P = d.paragraphs


def find(substr: str) -> int:
    for i, p in enumerate(P):
        if substr in p.text:
            return i
    raise ValueError(f"not found: {substr!r}")


def find_all(substr: str) -> list:
    return [i for i, p in enumerate(P) if substr in p.text]


def set_text(para: Paragraph, text: str):
    for r in list(para.runs):
        r._element.getparent().remove(r._element)
    para.add_run(text)


def remove_para(para: Paragraph):
    para._p.getparent().remove(para._p)


i_start = find("Kodi 7 e paraqet fragmentin operacional")
i_end = find_all("Tabela 12. Skema e VLAN-eve p\u00ebr t\u00eb kat\u00ebr switch-at")[-1]

# collect every paragraph AND the table element in between (the table sits
# right after the "Tabela 12 e p\u00ebrmbledh..." lead paragraph, before the
# empty marker paragraph and the caption).
to_remove_paras = [P[i] for i in range(i_start, i_end + 1)]

# find the <w:tbl> that belongs to this block (the one whose header cell
# reads "Switch") and remove it too.
target_tbl = None
for t in d.tables:
    if t.rows[0].cells[0].text.strip() == "Switch":
        target_tbl = t
        break
if target_tbl is not None:
    target_tbl._tbl.getparent().remove(target_tbl._tbl)
    print("removed Tabela 12 (VLAN scheme) table")
else:
    print("WARNING: Tabela 12 table not found")

for p in to_remove_paras:
    remove_para(p)
print(f"removed {len(to_remove_paras)} paragraphs (Kodi 7 + SW paragraph + Tabela 12)")

# re-snapshot after structural removal
P = d.paragraphs

# --- remove the front-matter "Tabela 12" entry in Lista e Tabelave
i_front_t12 = find("Tabela 12. Skema e VLAN-eve p\u00ebr t\u00eb kat\u00ebr switch-at")
remove_para(P[i_front_t12])
print("removed front-matter Tabela 12 entry")

P = d.paragraphs

# --- fix the closing synthesis paragraph: "Kodi 1-7" -> "Kodi 1-6",
#     "Tabela 11-12" -> "Tabela 11"
i_close = find("Kat\u00ebr lloje provash e mb\u00ebshtet\u00ebn k\u00ebt\u00eb punim")
old = P[i_close].text
new = (old
       .replace("Kodi 1\u20137", "Kodi 1\u20136")
       .replace("Tabela 11\u201312", "Tabela 11"))
set_text(P[i_close], new)
print("fixed closing paragraph cross-references")
print(new[:200])

d.save(DST)
print("Saved ->", DST)
