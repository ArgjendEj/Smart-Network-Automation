# -*- coding: utf-8 -*-
"""Third pass: v5 -> v6 (final). Adds a handful of grounded analysis
paragraphs (tied to the real screenshots/code already inserted) to close the
word-count gap without padding."""
from pathlib import Path

import docx
from docx.shared import Pt, RGBColor
from docx.oxml import OxmlElement
from docx.text.paragraph import Paragraph

SRC = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v5.docx")
DST = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v6.docx")

d = docx.Document(SRC)
P = d.paragraphs


def insert_para_after(ref: Paragraph, text="", italic=False, bold=False) -> Paragraph:
    new_p = OxmlElement("w:p")
    ref._p.addnext(new_p)
    new_para = Paragraph(new_p, ref._parent)
    run = new_para.add_run(text)
    run.italic = italic
    run.bold = bold
    return new_para


def find(substr: str) -> int:
    for i, p in enumerate(P):
        if substr in p.text:
            return i
    raise ValueError(f"not found: {substr!r}")


# --- 5.9: close with a note on OSPF+BGP simultaneously (ties to hypothesis)
i = find("Figura 9. Nd\u00ebrfaqja e modulit Manual Configuration")
insert_para_after(P[i],
    "Aktivizimi i OSPF-s\u00eb dhe i BGP-s\u00eb nj\u00ebkoh\u00ebsisht (Figura 9) prodhon dy blloqe "
    "t\u00eb pavarura n\u00eb konfigurimin e gjeneruar (router ospf 1 dhe router bgp <AS>), "
    "t\u00eb dyja duke i reklamuar t\u00eb nj\u00ebjtat rrjete lokale. Ky rast p\u00ebrdoret zakonisht "
    "p\u00ebr demonstrimin e migrimit ndaj skenar\u00ebve me shp\u00ebrndarje rrugësh (route "
    "redistribution) ose p\u00ebr krahasimin praktik t\u00eb kohes s\u00eb konvergjenc\u00ebs "
    "ndërmjet dy protokolleve mbi t\u00eb nj\u00ebjt\u00ebn topologji, pa pasur nevoj\u00eb t\u00eb "
    "rindërtohet konfigurimi nga fillimi p\u00ebr secilin protokoll.")

# --- 6.1: expand on the real Dashboard data
i = find("Figura 10. Dashboard-i me num\u00ebrimin e pajisjeve")
insert_para_after(P[i],
    "Dashboard-i i Figur\u00ebs 10 \u00ebsht\u00eb marr\u00eb nga nj\u00eb topologji reale prej 22 "
    "pajisjesh (2 routera, 4 switch-a, 8 PC, 4 telefona IP, 4 printer\u00eb), me 22 "
    "lidhje, nga t\u00eb cilat dy jan\u00eb router-me-router (redundante, seksioni 5.5.1). "
    "Tabela e adresimit e dashboard-it i ngjyros IP-t\u00eb sipas rolit: jeshile p\u00ebr "
    "gateway/menaxhim, portokalli p\u00ebr lidhjet router-me-router, dhe kalt\u00ebr p\u00ebr "
    "adres\u00ebn e vet\u00eb pajisjes fundore — nj\u00eb konventë vizuale q\u00eb e b\u00ebn t\u00eb "
    "menjëhershme dallimin midis nj\u00eb IP-je t\u00eb shtypur nga administratori "
    "(hand-typed) dhe nj\u00ebrës s\u00eb caktuar automatikisht.")

# --- 7.1.1: tie to the real Kodi 1 excerpt
i = find("Kufizimi i k\u00ebsaj qasjeje \u00ebsht\u00eb se ajo e supozon nj\u00eb strukturë")
insert_para_after(P[i],
    "Kodi 1 (seksioni 5.1) e ilustron pikën praktike të kësaj skeme: "
    "identifikuesi i VLAN-it nuk kërkon asnjë hap shtesë llogaritjeje nga "
    "administratori as gjatë krijimit, as gjatë leximit të konfigurimit më "
    "vonë — mjafton adresa e rrjetit për ta rikonstruktuar. Kjo e bën "
    "identifikuesin e parashikueshëm edhe kur administratori shikon "
    "drejtpërdrejt bazën e të dhënave ose logun e platformës, pa pasur "
    "nevojë për një regjistër të veçantë VLAN-esh të mbajtur paralelisht me "
    "dorë.")

# --- 7.2: one more interpretation paragraph, tied to the screenshots
i = find("Interpretimi i tret\u00eb \u00ebsht\u00eb se nd\u00ebrfaqja grafike")
insert_para_after(P[i],
    "Interpretimi i katërt lidhet me pamjen e përgjithshme të sistemit "
    "(Figura 3–Figura 10): çdo modul i rëndësishëm — kyçja, menaxhimi i "
    "pajisjeve, topologjia, Smart Auto Configuration, konfigurimi manual dhe "
    "dashboard-i — jeton në të njëjtën ndërfaqe, të shërbyer nga i njëjti "
    "proces FastAPI (seksioni 4.2). Kjo nuk është thjesht komoditet: e "
    "eliminon një klasë tjetër gabimesh operacionale, ato që lindin kur "
    "administratori duhet të kalojë mes disa mjeteve të veçanta (CLI për "
    "ekzekutim, një tabelë kalkulli për planin e adresimit, një depo Git për "
    "playbook-un) dhe humb sinkronizimin mes tyre.")

# --- 7.3: one more limitation paragraph
i = find("Kufizimi i kat\u00ebrt \u00ebsht\u00eb skema e adresimit")
insert_para_after(P[i],
    "Kufizimi i pest\u00eb ka t\u00eb b\u00ebj\u00eb me vlerësimin e p\u00ebrvojës s\u00eb p\u00ebrdorimit. "
    "Figurat 3–10 dëshmojnë se ndërfaqja funksionon dhe prodhon rezultate "
    "korrekte, por nuk përbëjnë provë të përdorshmërisë (usability) në "
    "kuptimin formal: nuk u realizua asnjë studim me pjesëmarrës të vërtetë "
    "që të maste, p.sh., kohën reale që një administrator fillestar do të "
    "kalonte duke mësuar ndërfaqen para se të arrinte shpejtësinë e "
    "modeluar në Kapitullin 6.")

d.save(DST)
print("Saved ->", DST)
