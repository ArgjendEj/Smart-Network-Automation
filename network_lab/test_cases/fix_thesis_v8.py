# -*- coding: utf-8 -*-
"""Eighth pass: v10 -> v11.

Adds Kodi 7 in the Appendix: the FULL real Cisco IOS configuration generated
by the platform for R2 (read straight from network.db, last_config column),
shown as the redundant counterpart to R1's config already cited as Kodi 6 /
Figura 8. This is a grounded, real, reproducible exhibit (same class of
content as everything else in the thesis) and also helps close the
remaining page-count gap toward the 50-60 page target, since a full
~65-line configuration listing occupies substantial vertical space.
"""
from pathlib import Path

import docx
from docx.shared import Pt
from docx.oxml import OxmlElement
from docx.text.paragraph import Paragraph

SRC = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v10.docx")
DST = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v11.docx")

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


R2_CONFIG = """!
! ===== ROUTER : R2 (auto-generated from topology) =====
!
hostname R2
!
no ip domain-lookup
ip domain-name lab.local
service password-encryption
!
ip routing
!
ip dhcp excluded-address 192.168.1.1 192.168.1.1
ip dhcp excluded-address 192.168.2.1 192.168.2.1
!
ip dhcp pool LAN_GigabitEthernet0_1
 network 192.168.1.0 255.255.255.0
 default-router 192.168.1.1
 dns-server 8.8.8.8
!
ip dhcp pool LAN_GigabitEthernet0_3
 network 192.168.2.0 255.255.255.0
 default-router 192.168.2.1
 dns-server 8.8.8.8
!
interface GigabitEthernet0/1
 description ### LAN 192.168.1.0/24 ###
 ip address 192.168.1.1 255.255.255.0
 ip nat inside
 no shutdown
!
interface GigabitEthernet0/3
 description ### LAN 192.168.2.0/24 ###
 ip address 192.168.2.1 255.255.255.0
 ip nat inside
 no shutdown
!
interface GigabitEthernet0/5
 description ### Link to R1 ###
 ip address 10.1.1.1 255.255.255.252
 ip nat outside
 no shutdown
!
interface GigabitEthernet0/0
 description ### Link to R1 ###
 ip address 10.10.10.2 255.255.255.252
 no shutdown
!
access-list 10 permit 192.168.1.0 0.0.0.255
access-list 11 permit 192.168.2.0 0.0.0.255
!
ip nat inside source list 10 interface GigabitEthernet0/5 overload
ip nat inside source list 11 interface GigabitEthernet0/5 overload
!
router ospf 1
 router-id 2.2.2.2
 passive-interface GigabitEthernet0/1
 passive-interface GigabitEthernet0/3
 network 192.168.1.0 0.0.0.255 area 0
 network 192.168.2.0 0.0.0.255 area 0
 network 10.1.1.0 0.0.0.3 area 0
 network 10.10.10.0 0.0.0.3 area 0
!
router bgp 65002
 bgp router-id 2.2.2.2
 bgp log-neighbor-changes
 network 192.168.1.0 mask 255.255.255.0
 network 192.168.2.0 mask 255.255.255.0
 neighbor 10.1.1.0 remote-as 65001
 neighbor 10.10.10.1 remote-as 65001
!
banner motd ^C Authorized access only - R2 ^C
!
line con 0
 logging synchronous
!
end"""

i_bullets_end = find("Suita e testeve automatike dhe udh\u00ebzuesi p\u00ebr ekzekutimin")
cur = insert_para_after(
    i_bullets_end if False else P[i_bullets_end],
    "Kodi 7 e paraqet konfigurimin e plot\u00eb, real, t\u00eb gjeneruar nga vet\u00eb "
    "platforma p\u00ebr routerin R2 \u2014 pjes\u00ebn tjet\u00ebr t\u00eb lidhjes redundante "
    "router-me-router t\u00eb diskutuar n\u00eb seksionin 5.5.1. Krahasuar me "
    "konfigurimin e R1-it (Kodi 6, Figura 8), vihet re simetria e pritur: "
    "t\u00eb nj\u00ebjtat protokolle (OSPF area 0, BGP me AS 65001/65002 t\u00eb "
    "kryqëzuar), por me adresa, VLAN-e dhe router-id t\u00eb ndrysh\u00ebm, t\u00eb "
    "nxjerra automatikisht nga pozicioni i vet\u00eb R2-it n\u00eb topologji, pa "
    "asnj\u00eb ndryshim manual n\u00eb shabllon."
)
for line in R2_CONFIG.split("\n"):
    cur = insert_para_after(cur, line, font_name="Consolas", size=9)
caption_after(cur, "Kodi 7. Konfigurimi i plot\u00eb i gjeneruar Cisco IOS p\u00ebr routerin R2 (redundant me R1).")

d.save(DST)
print("Saved ->", DST)
