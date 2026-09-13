# -*- coding: utf-8 -*-
"""Ninth pass: v11 -> v12.

Still closing the 50-60 page gap (currently 50 pages / 12,377 words after
the previous pass), with more grounded real content rather than filler:

- Kodi 8 / Kodi 9 in the Appendix: the full real switch configs for SW1 and
  SW2 (read from network.db), which demonstrate the deterministic VLAN
  function (Kodi 1, section 5.1) acting on two different LAN subnets behind
  the same router R1 (VLAN 100 for 192.168.10.0/24, VLAN 200 for
  192.168.20.0/24).
- Tabela 12: a compact real table cross-referencing every switch in the
  demo topology with its VLAN id/name and the subnet it serves.
"""
from pathlib import Path

import docx
from docx.shared import Pt
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

SRC = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v11.docx")
DST = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v12.docx")

d = docx.Document(SRC)
P = d.paragraphs


def find(substr: str) -> int:
    for i, p in enumerate(P):
        if substr in p.text:
            return i
    raise ValueError(f"not found: {substr!r}")


def insert_para_after(ref: Paragraph, text="", italic=False, bold=False,
                       font_name=None, size=None) -> Paragraph:
    new_p = OxmlElement("w:p")
    ref._p.addnext(new_p)
    new_para = Paragraph(new_p, ref._parent)
    if text:
        run = new_para.add_run(text)
        run.italic = italic
        run.bold = bold
        if font_name:
            run.font.name = font_name
        if size:
            run.font.size = Pt(size)
    return new_para


def caption_after(ref: Paragraph, text: str) -> Paragraph:
    p = insert_para_after(ref, text, italic=True)
    for r in p.runs:
        r.font.size = Pt(10)
    return p


def make_table_after(ref: Paragraph, headers, rows, col_widths_dxa):
    tbl = d.add_table(rows=1 + len(rows), cols=len(headers))
    tblPr = tbl._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:color"), "auto")
        el.set(qn("w:sz"), "4")
        borders.append(el)
    tblPr.append(borders)
    grid = tbl._tbl.find(qn("w:tblGrid"))
    for gc, w in zip(grid.findall(qn("w:gridCol")), col_widths_dxa):
        gc.set(qn("w:w"), str(w))
    hdr_cells = tbl.rows[0].cells
    for c, text in zip(hdr_cells, headers):
        c.text = text
        for p in c.paragraphs:
            for r in p.runs:
                r.bold = True
    for ridx, rowdata in enumerate(rows, start=1):
        cells = tbl.rows[ridx].cells
        for c, text in zip(cells, rowdata):
            c.text = str(text)
    ref._p.addnext(tbl._tbl)
    marker_p = OxmlElement("w:p")
    tbl._tbl.addnext(marker_p)
    return Paragraph(marker_p, ref._parent)


SW1_CONFIG = """!
! ===== SWITCH : SW1 (auto-generated from topology) =====
!
hostname SW1
!
no ip domain-lookup
!
spanning-tree mode pvst
!
vlan 100
 name DATA_VLAN100
!
interface FastEthernet0/1
 description ### Uplink to R1 - DATA_VLAN100 (192.168.10.0/24) ###
 switchport mode access
 switchport access vlan 100
 no shutdown
!
interface range FastEthernet0/1-24
 description ### DATA_VLAN100 access ###
 switchport mode access
 switchport access vlan 100
 spanning-tree portfast
 no shutdown
!
banner motd ^C Authorized access only - SW1 ^C
!
line con 0
 logging synchronous
!
end"""

SW2_CONFIG = """!
! ===== SWITCH : SW2 (auto-generated from topology) =====
!
hostname SW2
!
no ip domain-lookup
!
spanning-tree mode pvst
!
vlan 200
 name DATA_VLAN200
!
interface FastEthernet0/1
 description ### Uplink to R1 - DATA_VLAN200 (192.168.20.0/24) ###
 switchport mode access
 switchport access vlan 200
 no shutdown
!
interface range FastEthernet0/1-24
 description ### DATA_VLAN200 access ###
 switchport mode access
 switchport access vlan 200
 spanning-tree portfast
 no shutdown
!
banner motd ^C Authorized access only - SW2 ^C
!
line con 0
 logging synchronous
!
end"""

i_kodi7_cap = find("Kodi 7. Konfigurimi i plot\u00eb i gjeneruar Cisco IOS p\u00ebr routerin R2")
cur = insert_para_after(
    P[i_kodi7_cap],
    "Kodi 8 dhe Kodi 9 e ilustrojn\u00eb funksionin _vlan_for() (Kodi 1, "
    "seksioni 5.1) n\u00eb praktik\u00eb, mbi dy nga switch-at e t\u00eb nj\u00ebjt\u00ebs "
    "topologji demonstruese: SW1 i sh\u00ebrben nënrrjetit 192.168.10.0/24 t\u00eb "
    "lidhur me R1 dhe merr VLAN 100, ndërsa SW2 i sh\u00ebrben nënrrjetit "
    "192.168.20.0/24, gjithashtu t\u00eb lidhur me R1, dhe merr VLAN 200 \u2014 "
    "saktësisht okteti i tret\u00eb i secilit nënrrjet, shumëzuar me 10, ashtu "
    "siç e p\u00ebrshkruan rreshti 6 i Kodit 1."
)
for line in SW1_CONFIG.split("\n"):
    cur = insert_para_after(cur, line, font_name="Consolas", size=9)
cur = caption_after(cur, "Kodi 8. Konfigurimi i plot\u00eb i gjeneruar Cisco IOS p\u00ebr switch-in SW1 (VLAN 100).")
for line in SW2_CONFIG.split("\n"):
    cur = insert_para_after(cur, line, font_name="Consolas", size=9)
cur = caption_after(cur, "Kodi 9. Konfigurimi i plot\u00eb i gjeneruar Cisco IOS p\u00ebr switch-in SW2 (VLAN 200).")

SWITCH_VLANS = [
    ("SW1", "100", "DATA_VLAN100", "192.168.10.0/24", "R1"),
    ("SW2", "200", "DATA_VLAN200", "192.168.20.0/24", "R1"),
    ("SW1.1", "10", "DATA_VLAN10", "192.168.1.0/24", "R2"),
    ("SW2.2", "20", "DATA_VLAN20", "192.168.2.0/24", "R2"),
]
lead = insert_para_after(
    cur,
    "Tabela 12 e p\u00ebrmbledh skem\u00ebn e plot\u00eb t\u00eb VLAN-eve p\u00ebr t\u00eb kat\u00ebr "
    "switch-at e topologjis\u00eb demonstruese, duke konfirmuar q\u00eb identifikuesi "
    "i VLAN-it \u00ebsht\u00eb gjithmon\u00eb i nxjerr deterministikisht nga nënrrjeti, "
    "pavarësisht se cilit router i \u00ebsht\u00eb i lidhur switch-i."
)
tbl_marker = make_table_after(
    lead,
    ["Switch", "VLAN", "Emri i VLAN-it", "N\u00ebnrrjeti", "Router uplink"],
    SWITCH_VLANS,
    [1400, 900, 2200, 2200, 1700],
)
caption_after(tbl_marker, "Tabela 12. Skema e VLAN-eve p\u00ebr t\u00eb kat\u00ebr switch-at e topologjis\u00eb demonstruese.")

i_front_t11 = find("Tabela 11. Inventari i plot\u00eb i pajisjeve n\u00eb topologjin\u00eb demonstruese.")
insert_para_after(P[i_front_t11], "Tabela 12. Skema e VLAN-eve p\u00ebr t\u00eb kat\u00ebr switch-at e topologjis\u00eb demonstruese.")

d.save(DST)
print("Saved ->", DST)
