# -*- coding: utf-8 -*-
"""Twentieth pass (v2 - corrected): v25 -> v26.

The first attempt at this used inline_shapes[index] to identify which
picture to replace, matched against runs via lxml element `is` identity.
That mapping turned out to be unreliable (verified by inspection: it
replaced the WRONG image for the flow-diagram, leaving the actually
broken one -- still showing the stale baked-in "Figura 4" caption --
untouched, while corrupting an unrelated image). This version instead
walks the document in order and matches each picture run to the REAL
caption paragraph that follows it in the text, which is unambiguous.
"""
from pathlib import Path

import docx
from docx.oxml.ns import qn

SRC = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v25 (1).docx")
DST = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v26.docx")
FIG = Path(r"C:\Users\armen\OneDrive\Desktop\Smart Network Automation\network_lab\test_cases")

TARGETS = {
    "Figura 1. Arkitektura tri-shtresore": FIG / "figura1_arkitektura.png",
    "Figura 2. Skema relacionale e baz\u00ebs": FIG / "figura2_skema_db.png",
    "Figura 6. Rrjedha e plot\u00eb e procesit": FIG / "figura4_flow.png",
}

d = docx.Document(SRC)
P = d.paragraphs

# find every (run_with_drawing, following_caption_text) pair
picture_runs = []  # list of (run, drawing_el, caption_text, paragraph_index)
for pi, p in enumerate(P):
    for r in p.runs:
        drawings = r._element.findall(qn("w:drawing"))
        if not drawings:
            continue
        cap = ""
        for j in range(pi + 1, min(pi + 4, len(P))):
            if P[j].text.strip():
                cap = P[j].text.strip()
                break
        picture_runs.append((r, drawings[0], cap, pi))

print(f"found {len(picture_runs)} picture-bearing runs total")

replaced = 0
for r, drawing, cap, pi in picture_runs:
    for prefix, newfile in TARGETS.items():
        if cap.startswith(prefix):
            extent = drawing.find(".//" + qn("wp:extent"))
            cx = int(extent.get("cx"))  # EMU
            for child in list(r._element):
                r._element.remove(child)
            r.add_picture(str(newfile), width=cx)
            print(f"replaced image before caption: {cap[:55]!r} (width EMU={cx})")
            replaced += 1

print(f"replaced {replaced} images (expected 3)")
assert replaced == 3

# ---------------------------------------------------------------- text fix
fixed = 0
for p in P:
    if "inventari i plotë i pajisjeve e i VLAN-eve i lexuar" in p.text:
        full_text = "".join(r.text for r in p.runs)
        if "e i VLAN-eve " in full_text:
            new_full = full_text.replace("e i VLAN-eve ", "", 1)
            if p.runs:
                p.runs[0].text = new_full
                for r in p.runs[1:]:
                    r.text = ""
            fixed += 1
print(f"fixed {fixed} stale VLAN-table cross-reference(s)")

d.save(DST)
print("Saved ->", DST)
