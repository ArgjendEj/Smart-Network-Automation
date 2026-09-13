# -*- coding: utf-8 -*-
"""Seventh pass: v9 -> v10.

1) STRUCTURAL FIX (important correctness bug): three earlier passes used a
   plain find() (first match) instead of find_all()[-1] (last/body match) to
   locate their anchor paragraph. Because the anchor text also exists in the
   front-matter "Lista e Figurave" / "Lista e Tabelave" blocks (which appear
   earlier in the paragraph list than the body), the following ended up
   physically embedded INSIDE the front-matter lists instead of the body:
     - The whole "Kodi 1" code block (intro + 14 code lines + caption +
       explanation, 17 paragraphs) landed inside LISTA E TABELAVE, between
       the Tabela 6 and Tabela 7 entries.
     - The OSPF/BGP paragraph landed inside LISTA E FIGURAVE, between the
       Figura 9 and Figura 10 entries.
     - The Dashboard paragraph landed inside LISTA E FIGURAVE, right after
       the Figura 10 entry.
   This pass moves all of them (as XML elements, so formatting/fonts are
   preserved exactly) to their correct position in the BODY, after the real
   captions in section 5.1 / 5.9 / 6.1, and leaves the front-matter lists
   containing only caption lines again.

2) Adds a new real, grounded table (Tabela 11): the full 22-device inventory
   of the demonstration topology used throughout the figures/results
   (read from the live network.db), with hostname/type/management IP per
   device. Registered in "Lista e Tabelave" too.

3) Modestly enlarges the embedded screenshots/diagrams (page-growth lever
   that does not add words), to help reach the 50-60 page target.
"""
from pathlib import Path

import docx
from docx.shared import Inches, Pt, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

SRC = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v9.docx")
DST = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v10.docx")

d = docx.Document(SRC)
P = d.paragraphs


def find(substr: str) -> int:
    for i, p in enumerate(P):
        if substr in p.text:
            return i
    raise ValueError(f"not found: {substr!r}")


def find_all(substr: str) -> list:
    return [i for i, p in enumerate(P) if substr in p.text]


def insert_para_after(ref: Paragraph, text="", italic=False, bold=False,
                       align=None) -> Paragraph:
    new_p = OxmlElement("w:p")
    ref._p.addnext(new_p)
    new_para = Paragraph(new_p, ref._parent)
    if text:
        run = new_para.add_run(text)
        run.italic = italic
        run.bold = bold
    if align is not None:
        new_para.alignment = align
    return new_para


def caption_after(ref: Paragraph, text: str) -> Paragraph:
    p = insert_para_after(ref, text, italic=True)
    for r in p.runs:
        r.font.size = Pt(10)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return p


# ===================================================================
# 1. STRUCTURAL FIX: move misplaced blocks out of the front-matter lists
# ===================================================================

# --- 1a. The stray OSPF/BGP paragraph (currently between Figura 9 / Figura 10
#     entries in Lista e Figurave) -> move after the REAL body Figura 9 caption
#     (end of section 5.9).
i_stray_ospf = find("Aktivizimi i OSPF-s\u00eb dhe i BGP-s\u00eb nj\u00ebkoh\u00ebsisht")
stray_ospf = P[i_stray_ospf]
i_body_fig9 = find_all("Figura 9. Nd\u00ebrfaqja e modulit Manual Configuration")[-1]
body_fig9 = P[i_body_fig9]
body_fig9._p.addnext(stray_ospf._p)
print("moved stray OSPF paragraph after body Figura 9 caption")

# --- 1b. The stray Dashboard paragraph (currently right after the Figura 10
#     entry in Lista e Figurave) -> move after the REAL body Figura 10 caption
#     (section 6.1).
i_stray_dash = find("Dashboard-i i Figur\u00ebs 10 \u00ebsht\u00eb marr\u00eb nga nj\u00eb topologji reale")
stray_dash = P[i_stray_dash]
i_body_fig10 = find_all("Figura 10. Dashboard-i me num\u00ebrimin e pajisjeve")[-1]
body_fig10 = P[i_body_fig10]
body_fig10._p.addnext(stray_dash._p)
print("moved stray Dashboard paragraph after body Figura 10 caption")

# --- 1c. The whole Kodi 1 block (intro, 14 code lines, caption, explanation)
#     currently sits inside Lista e Tabelave, between Tabela 6 and Tabela 7.
#     Move it after the REAL body Tabela 6 caption (section 5.1).
i_kodi1_intro = find("Kodi 1 e paraqet funksionin q\u00eb e zbaton skem\u00ebn deterministike")
i_kodi1_explan = find("Rreshti 6 e trajton rastin e zakonsh\u00ebm")
# the block is contiguous in the CURRENT tree: collect the actual sibling
# elements between (and including) intro and explanation, in document order.
block_paras = []
node = P[i_kodi1_intro]._p
end_node = P[i_kodi1_explan]._p
while True:
    block_paras.append(node)
    if node is end_node:
        break
    node = node.getnext()

i_body_tabela6 = find_all("Tabela 6. Rolet e serverit dhe efekti i tyre")[-1]
anchor = P[i_body_tabela6]._p
for node in block_paras:
    anchor.addnext(node)
    anchor = node
print(f"moved Kodi 1 block ({len(block_paras)} paragraphs) after body Tabela 6 caption")

# ===================================================================
# 2. Re-snapshot paragraphs (positions changed) before adding new content
# ===================================================================
P = d.paragraphs


def find2(substr: str) -> int:
    for i, p in enumerate(P):
        if substr in p.text:
            return i
    raise ValueError(f"not found: {substr!r}")


def find_all2(substr: str) -> list:
    return [i for i, p in enumerate(P) if substr in p.text]


def make_table_after(ref: Paragraph, headers, rows, col_widths_dxa):
    """Build a table with the same manual border style as the rest of the
    thesis, then splice it into the body right after `ref`."""
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
    # splice: python-docx just appended it at the end of the document body;
    # move its <w:tbl> element to right after `ref`.
    ref._p.addnext(tbl._tbl)
    # python-docx requires a paragraph after a table at the very end of a
    # body/cell in some contexts; here it's mid-body so no extra para needed.
    # Return a Paragraph wrapper for the last cell's last paragraph won't
    # help chaining afterwards, so return a fresh marker paragraph placed
    # right after the table instead.
    marker_p = OxmlElement("w:p")
    tbl._tbl.addnext(marker_p)
    return Paragraph(marker_p, ref._parent)


# ===================================================================
# 3. New Tabela 11: real 22-device inventory (from network.db), placed in
#    section 6.1 right after the (now correctly positioned) Dashboard
#    paragraph.
# ===================================================================
DEVICES = [
    ("R1", "router", "192.168.100.1"),
    ("R2", "router", "192.168.200.1"),
    ("SW1", "switch", "\u2013"),
    ("SW2", "switch", "\u2013"),
    ("SW1.1", "switch", "\u2013"),
    ("SW2.2", "switch", "\u2013"),
    ("PC1", "pc", "192.168.10.3"),
    ("PC2", "pc", "192.168.10.4"),
    ("PC1.1", "pc", "192.168.1.3"),
    ("PC2.2", "pc", "192.168.1.4"),
    ("PC3", "pc", "192.168.20.3"),
    ("PC4", "pc", "192.168.20.4"),
    ("PC3.3", "pc", "192.168.2.3"),
    ("PC4.4", "pc", "192.168.2.4"),
    ("IPH1", "ip_phone", "192.168.10.2"),
    ("IPH2", "ip_phone", "192.168.20.2"),
    ("IPH1.1", "ip_phone", "192.168.1.2"),
    ("IPH2.2", "ip_phone", "192.168.2.2"),
    ("Print1", "printer", "192.168.10.5"),
    ("Print2", "printer", "192.168.20.5"),
    ("Print1.1", "printer", "192.168.1.5"),
    ("Print2.2", "printer", "192.168.2.5"),
]

i_after_dash = find2("Dashboard-i i Figur\u00ebs 10 \u00ebsht\u00eb marr\u00eb nga nj\u00eb topologji reale")
p_after_dash = P[i_after_dash]
lead = insert_para_after(
    p_after_dash,
    "Tabela 11 e detajon inventarin e plot\u00eb t\u00eb k\u00ebsaj topologjie demonstruese, "
    "ashtu si\u00eb \u00ebsht\u00eb lexuar drejtp\u00ebrdrejt nga baza e t\u00eb dh\u00ebnave (network.db) "
    "n\u00eb kohën e kapjes s\u00eb Figur\u00ebs 5 dhe Figur\u00ebs 10: emri i pajisjes, lloji dhe "
    "adresa e menaxhimit (kur ekziston \u2014 switch-at n\u00eb k\u00ebt\u00eb topologji nuk kan\u00eb "
    "IP menaxhimi t\u00eb veçant\u00eb, siç pritet nga rregulli i par\u00eb i motorit t\u00eb "
    "konfigurimit, seksioni 5.1)."
)
tbl_marker = make_table_after(
    lead,
    ["Emri i pajisjes", "Lloji", "Adresa e menaxhimit"],
    DEVICES,
    [3200, 2400, 2800],
)
caption_after(tbl_marker, "Tabela 11. Inventari i plot\u00eb i pajisjeve n\u00eb topologjin\u00eb demonstruese (22 pajisje).")

# --- register Tabela 11 in the front-matter Lista e Tabelave (after Tabela 10)
i_front_t10 = find_all2("Tabela 10. Shp\u00ebrndarja e gabimeve sipas kategoris\u00eb")[0]
insert_para_after(P[i_front_t10], "Tabela 11. Inventari i plot\u00eb i pajisjeve n\u00eb topologjin\u00eb demonstruese.")

# ===================================================================
# 4. Enlarge embedded figures (page-growth lever; no extra words)
# ===================================================================
# usable text width is 6.268in; keep a small margin below that.
NEW_WIDTHS_IN = {
    2: 6.10,   # Figura 1 - arkitektura
    3: 6.10,   # Figura 2 - skema DB
    4: 4.00,   # Figura 3 - login (was 3.2)
    5: 5.90,   # Figura 4 - devices (tall)
    6: 6.10,   # Figura 5/6 area
    7: 6.10,
    8: 6.10,
    9: 5.40,   # was 4.6 (manual config)
    10: 5.85,  # very tall (topology)
    11: 6.10,
    12: 6.10,
}
shapes = d.inline_shapes
for idx, new_w_in in NEW_WIDTHS_IN.items():
    shp = shapes[idx]
    old_w = shp.width
    old_h = shp.height
    aspect = old_h / old_w
    new_w = Emu(int(Inches(new_w_in)))
    new_h = Emu(int(new_w * aspect))
    shp.width = new_w
    shp.height = new_h

d.save(DST)
print("Saved ->", DST)
