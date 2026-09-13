# -*- coding: utf-8 -*-
"""Tenth pass: v12 -> v13.

User feedback: too much raw code at the end (Appendix) — trim it down and
replace with more analytical text instead.

- Kodi 7 (R2): keep only the operational middle of the config (interfaces,
  NAT/ACL, OSPF, BGP) and drop the boilerplate head (hostname/DHCP pools)
  and tail (banner/line con/end). Caption changed from "i plotë" (full) to
  "fragment". Intro paragraph rewritten with more concrete comparative
  detail (router-id/AS/neighbor values, real line counts) instead of just
  restating what code is coming.
- Kodi 8 / Kodi 9 (SW1/SW2 full configs): REMOVED entirely. The shared
  intro paragraph is rewritten into a fuller analytical paragraph that
  conveys the same facts in prose, pointing at Tabela 12 (which already
  carries the concrete VLAN/subnet data) instead of showing raw code again.
"""
from pathlib import Path

import docx
from docx.shared import Pt
from docx.oxml import OxmlElement
from docx.text.paragraph import Paragraph

SRC = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v12.docx")
DST = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v13.docx")

d = docx.Document(SRC)
P = d.paragraphs


def find(substr: str) -> int:
    for i, p in enumerate(P):
        if substr in p.text:
            return i
    raise ValueError(f"not found: {substr!r}")


def set_text(para: Paragraph, text: str, italic=False, bold=False):
    for r in list(para.runs):
        r._element.getparent().remove(r._element)
    run = para.add_run(text)
    run.italic = italic
    run.bold = bold


def remove_para(para: Paragraph):
    para._p.getparent().remove(para._p)


def insert_para_after(ref: Paragraph, text="", italic=False, font_name=None, size=None) -> Paragraph:
    new_p = OxmlElement("w:p")
    ref._p.addnext(new_p)
    new_para = Paragraph(new_p, ref._parent)
    if text:
        run = new_para.add_run(text)
        run.italic = italic
        if font_name:
            run.font.name = font_name
        if size:
            run.font.size = Pt(size)
    return new_para


# ------------------------------------------------------------ locate block
i_intro = find("Kodi 7 e paraqet konfigurimin e plot\u00eb")
i_iface_start = find("interface GigabitEthernet0/1")
# make sure this is the R2 one (there are earlier interface blocks for R1
# too, but those are inside Kodi 6 / Figura 8, well before this point) —
# search only from i_intro forward.
i_iface_start = next(i for i in range(i_intro, len(P)) if P[i].text.strip() == "interface GigabitEthernet0/1")
i_neighbor_last = next(i for i in range(i_intro, len(P)) if "neighbor 10.10.10.1 remote-as 65001" in P[i].text)
i_kodi7_cap = find("Kodi 7. Konfigurimi i plot\u00eb i gjeneruar Cisco IOS p\u00ebr routerin R2")
i_sw_intro = find("Kodi 8 dhe Kodi 9 e ilustrojn\u00eb funksionin _vlan_for()")
i_sw2_cap = find("Kodi 9. Konfigurimi i plot\u00eb i gjeneruar Cisco IOS p\u00ebr switch-in SW2")

# ------------------------------------------------------------ 1. rewrite Kodi 7 intro
set_text(P[i_intro],
    "Kodi 7 e paraqet fragmentin operacional (interface-t, NAT/ACL, OSPF dhe "
    "BGP) nga konfigurimi i gjeneruar automatikisht p\u00ebr routerin R2 \u2014 "
    "pjes\u00ebn m\u00eb t\u00eb ndjeshme t\u00eb lidhjes redundante router-me-router t\u00eb "
    "diskutuar n\u00eb seksionin 5.5.1; hyrja e zakonshme (hostname, DHCP pool-et) "
    "dhe mbyllja standarde (banner, line con) jan\u00eb hequr p\u00ebr shkurtësi, pasi "
    "nuk ndryshojn\u00eb n\u00eb thelb nga router n\u00eb router. Krahasuar me R1-in (Kodi 6, "
    "Figura 8), R2 merr router-id 2.2.2.2 dhe AS 65002 (kund\u00ebr 1.1.1.1 dhe AS "
    "65001 p\u00ebr R1); OSPF-ja i reklamon t\u00eb katra rrjetet e veta (dy LAN lokale "
    "dhe dy lidhjet /30 me R1) n\u00eb area 0, ndërsa BGP-ja krijon dy fqinj\u00ebsi "
    "eBGP drejt R1-it, nj\u00eb p\u00ebr secil\u00ebn lidhje redundante. Asnj\u00eb nga k\u00ebto "
    "vlera \u2014 router-id, numri AS, adresat e fqinj\u00ebve \u2014 nuk shtypet me dor\u00eb: "
    "t\u00eb gjitha nxirren automatikisht nga pozicioni i R2-it n\u00eb topologji, sipas "
    "t\u00eb nj\u00ebjtit shabllon Jinja2 (Kodi 4) q\u00eb p\u00ebrdoret p\u00ebr çdo router tjet\u00ebr. "
    "Konfigurimi i plot\u00eb i R2-it ka 66 rreshta gjithsej."
)

# ------------------------------------------------------------ 2. trim the code:
# delete everything between the intro and "interface GigabitEthernet0/1"
# (the hostname/DHCP boilerplate), and everything between the BGP neighbor
# line and the Kodi 7 caption (the banner/line con/end boilerplate).
head_junk = [P[i] for i in range(i_intro + 1, i_iface_start)]
tail_junk = [P[i] for i in range(i_neighbor_last + 1, i_kodi7_cap)]
for p in head_junk:
    remove_para(p)
for p in tail_junk:
    remove_para(p)

# ------------------------------------------------------------ 3. re-caption Kodi 7
set_text(P[i_kodi7_cap],
    "Kodi 7. Fragmenti operacional (interface, NAT/ACL, OSPF, BGP) i "
    "konfigurimit Cisco IOS t\u00eb gjeneruar p\u00ebr routerin R2.", italic=True)

# ------------------------------------------------------------ 4. remove SW1/SW2 code entirely
sw_junk = [P[i] for i in range(i_sw_intro + 1, i_sw2_cap + 1)]
for p in sw_junk:
    remove_para(p)

# ------------------------------------------------------------ 5. rewrite the SW intro into full prose analysis
set_text(P[i_sw_intro],
    "Skema e VLAN-eve e Tabel\u00ebs 12 e konfirmon t\u00eb nj\u00ebjtin parim mbi "
    "switch-at e topologjis\u00eb: funksioni _vlan_for() (Kodi 1, seksioni 5.1) "
    "e nxjerr identifikuesin e VLAN-it drejtp\u00ebrdrejt nga okteti i tret\u00eb i "
    "n\u00ebnrrjetit lokal, shum\u00ebzuar me 10, pa asnj\u00eb regjist\u00ebr t\u00eb ve\u00e7ant\u00eb t\u00eb "
    "mbajtur me dor\u00eb. SW1 dhe SW2 jan\u00eb t\u00eb dy t\u00eb lidhur me R1, por i "
    "sh\u00ebrbejn\u00eb dy n\u00ebnrrjeteve t\u00eb ndryshme (192.168.10.0/24 dhe "
    "192.168.20.0/24) dhe marrin p\u00ebrkat\u00ebsisht VLAN 100 dhe VLAN 200; "
    "SW1.1 dhe SW2.2, t\u00eb lidhur me R2, ndjekin t\u00eb nj\u00ebjt\u00ebn logjik\u00eb mbi "
    "n\u00ebnrrjetet 192.168.1.0/24 dhe 192.168.2.0/24, duke marr\u00eb VLAN 10 dhe "
    "VLAN 20. Konfigurimi i gjeneruar p\u00ebr nj\u00eb switch tipik ka rreth 25 "
    "rreshta \u2014 hostname, spanning-tree, deklarimi i VLAN-it dhe dy blloqe "
    "interface-esh, nj\u00ebri p\u00ebr portin e uplink-ut dhe tjetri p\u00ebr diapazonin e "
    "porteve t\u00eb aksesit \u2014 identik nga nj\u00ebri switch te tjetri, me p\u00ebrjashtim "
    "t\u00eb numrit t\u00eb VLAN-it dhe t\u00eb n\u00ebnrrjetit t\u00eb cituar n\u00eb p\u00ebrshkrimet e "
    "interface-ve. Kjo simetri e plot\u00eb \u2014 katër switch, katër VLAN t\u00eb "
    "ndryshme, i njëjti shabllon \u2014 \u00ebsht\u00eb pikërisht ajo q\u00eb e b\u00ebn praktike "
    "shtimin e degëve t\u00eb reja n\u00eb topologji pa u dashur t\u00eb rishkruhet asnj\u00eb "
    "rregull konfigurimi (seksioni 7.1.1)."
)

d.save(DST)
print("Saved ->", DST)
