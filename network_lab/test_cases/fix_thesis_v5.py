# -*- coding: utf-8 -*-
"""Fifth pass: v7 -> v8 (final). One more grounded paragraph listing real
test cases, to close the remaining word-count gap."""
from pathlib import Path

import docx
from docx.oxml import OxmlElement
from docx.text.paragraph import Paragraph

SRC = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v7.docx")
DST = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v8.docx")

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


i = find("Ekzekutimi i suit\u00ebs")
insert_para_after(P[i],
    "Disa raste konkrete ilustrojn\u00eb thell\u00ebsin\u00eb e testeve: "
    "test_router_carries_several_hand_typed_lan_gateways e verifikon q\u00eb nj\u00eb "
    "router mund t\u00eb mbaj\u00eb disa gateway LAN t\u00eb shtypura me dor\u00eb dhe q\u00eb "
    "secili switch i ri i lidhur i konsumon ato n\u00eb radh\u00eb; "
    "test_two_links_between_the_same_pair_of_routers e verifikon q\u00eb dy "
    "lidhje t\u00eb pavarura router-me-router marrin dy /30 t\u00eb ndryshme dhe nuk "
    "bashkohen n\u00eb nj\u00eb rigjenerim t\u00eb dyt\u00eb; ndërsa "
    "test_server_dhcp_role_makes_routers_relay e verifikon q\u00eb kur nj\u00eb "
    "server deklarohet me rolin DHCP, routeri e h\u00ebq automatikisht pool-in "
    "e vet lokal dhe e zëvendëson me nj\u00eb direktiv\u00eb ip helper-address drejt "
    "serverit. Kjo shkall\u00eb granulariteti testesh reflekton natyr\u00ebn e "
    "rregullave t\u00eb motorit t\u00eb konfigurimit (seksioni 5.1): secila rregull\u00eb "
    "e dokumentuar n\u00eb prozë ka nj\u00eb ose m\u00eb shum\u00eb teste q\u00eb e detyrojn\u00eb "
    "sjelljen e saj.")

d.save(DST)
print("Saved ->", DST)
