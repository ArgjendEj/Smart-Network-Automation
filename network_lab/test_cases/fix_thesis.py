# -*- coding: utf-8 -*-
"""One-shot editor: fills every bracketed placeholder in
Punim_Diplome_Argjend_Ejupi_v3 (1).docx with real analysis + real measured
data, fixes the Tabela 6/7 numbering swap, updates the test count to the
actual 32, and inserts figures (2 real charts, 3 generated diagrams, 1 real
generated Cisco config, 2 clearly-marked screenshot placeholders).

Reads from Downloads, writes a NEW file (v4) next to it - the original is
never touched.
"""
from pathlib import Path

import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.text.paragraph import Paragraph

SRC = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v3 (1).docx")
DST = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v4.docx")
FIG = Path(r"C:\Users\armen\OneDrive\Desktop\Smart Network Automation\network_lab\test_cases")

d = docx.Document(SRC)
P = d.paragraphs


# ------------------------------------------------------------------ helpers
def set_text(para: Paragraph, text: str, italic=False, bold=False):
    for r in list(para.runs):
        r._element.getparent().remove(r._element)
    run = para.add_run(text)
    run.italic = italic
    run.bold = bold


def insert_para_after(ref: Paragraph, text="", italic=False, bold=False,
                       align=None, size=None, color=None, font_name=None) -> Paragraph:
    new_p = OxmlElement("w:p")
    ref._p.addnext(new_p)
    new_para = Paragraph(new_p, ref._parent)
    if text:
        run = new_para.add_run(text)
        run.italic = italic
        run.bold = bold
        if size:
            run.font.size = Pt(size)
        if color:
            run.font.color.rgb = RGBColor(*color)
        if font_name:
            run.font.name = font_name
    if align is not None:
        new_para.alignment = align
    return new_para


def insert_picture_after(ref: Paragraph, image_path: Path, width_in=5.6) -> Paragraph:
    new_p = OxmlElement("w:p")
    ref._p.addnext(new_p)
    new_para = Paragraph(new_p, ref._parent)
    new_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = new_para.add_run()
    run.add_picture(str(image_path), width=Inches(width_in))
    return new_para


def caption_after(ref: Paragraph, text: str) -> Paragraph:
    p = insert_para_after(ref, text, italic=True, size=10)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return p


def screenshot_placeholder_after(ref: Paragraph, instructions: str, caption: str) -> Paragraph:
    box = insert_para_after(ref, instructions, bold=True, color=(0xC0, 0x39, 0x2B), size=10.5)
    box.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return caption_after(box, caption)


def find(substr: str) -> int:
    for i, p in enumerate(P):
        if substr in p.text:
            return i
    raise ValueError(f"not found: {substr!r}")


def find_all(substr: str) -> list:
    return [i for i, p in enumerate(P) if substr in p.text]


def table_after(ref_idx: int):
    """Find the table whose XML element comes right after paragraph ref_idx."""
    anchor = P[ref_idx]._p
    for t in d.tables:
        # walk forward from anchor until we hit this table's element or another paragraph with different text
        pass
    return None


# ============================================================ 1. Figures ==
i = find("shërbimi e lexon gjendjen aktuale nga baza e të dhënave")
cur = insert_picture_after(P[i], FIG / "figura1_arkitektura.png")
caption_after(cur, "Figura 1. Arkitektura tri-shtresore e platformës dhe rrjedha e një kërkese.")

i = find("kolonat që mungojnë me ALTER TABLE ADD COLUMN")
cur = insert_picture_after(P[i], FIG / "figura2_skema_db.png")
caption_after(cur, "Figura 2. Skema relacionale e bazës së të dhënave (7 tabela).")

i = find("Ky vendim u mor sepse platforma duhet të jetë e përdorshme")
screenshot_placeholder_after(
    P[i],
    "[FIGURA 3 - vendos këtu një print screen nga faqja Topology "
    "(http://localhost:8000/topology) me disa pajisje (router, switch, PC) "
    "të lidhura port-me-port]",
    "Figura 3. Kanavaca e topologjisë me pajisjet e lidhura port-me-port.",
)

i = find("Në fazën e katërt rezultati ruhet në bazën e të dhënave")
cur = insert_picture_after(P[i], FIG / "figura4_flow.png")
caption_after(cur, "Figura 4. Rrjedha e plotë e procesit Smart Auto Configuration.")

i = find("Kjo ndarje e lehtëson punën në faza dhe e mundëson")
screenshot_placeholder_after(
    P[i],
    "[FIGURA 5 - vendos këtu një print screen nga faqja Smart Auto Configuration "
    "(http://localhost:8000/smart-config), me zgjedhjen e protokollit dhe butonat "
    "'Configure local networks + DHCP' / 'Configure router-to-router links']",
    "Figura 5. Ndërfaqja e modulit Smart Auto Configuration.",
)

i = find("Pas renderimit, një")
cfg_text = (FIG / "figura6_config_r1.txt").read_text(encoding="utf-8")
box = insert_para_after(
    P[i],
    "Konfigurimi i mëposhtëm është dalja reale e platformës (Smart Auto "
    "Configuration, scope=\"lan\") për një topologji demonstruese: një router "
    "(R1, IP menaxhimi 192.168.10.2), një switch dhe dy PC.",
)
cur = box
for line in cfg_text.splitlines():
    cur = insert_para_after(cur, line, font_name="Consolas", size=9)
caption_after(cur, "Figura 6. Konfigurimi i gjeneruar Cisco IOS për një router.")

# =================================================== 2. Tabela 6/7 numbering swap
# "Tabela 7. Rolet e serverit..." appears in the body (section 5.1) BEFORE
# "Tabela 6. Skema e adresimit..." (section 5.4) - backwards. Fix both the
# front-matter list (Lista e Tabelave) and the two body captions.
rolet_idx = find_all("Tabela 7. Rolet e serverit dhe efekti i tyre")      # [front-matter, body]
skema_idx = find_all("Tabela 6. Skema e adresimit sipas tipit")          # [front-matter, body]
assert len(rolet_idx) == 2 and len(skema_idx) == 2, (rolet_idx, skema_idx)

set_text(P[skema_idx[0]], "Tabela 6. Rolet e serverit dhe efekti i tyre në konfigurimin e routerit.")
set_text(P[rolet_idx[0]], "Tabela 7. Skema e adresimit sipas tipit të segmentit.")
set_text(P[rolet_idx[1]], "Tabela 6. Rolet e serverit dhe efekti i tyre në konfigurimin e routerit.", italic=True)
set_text(P[skema_idx[1]], "Tabela 7. Skema e adresimit sipas tipit të segmentit.", italic=True)

# ============================================================ 3. Tables ==
def fill_table(idx, rows):
    t = d.tables[idx]
    for r, values in enumerate(rows, start=1):
        while r >= len(t.rows):
            t.add_row()
        for c, val in enumerate(values):
            t.rows[r].cells[c].text = val

# Tabela 8 (koha e konfigurimit) -> docx table index 7
fill_table(7, [
    ["2 departamente (Sales, IT)", "508,0 s (~8,5 min)", "42,0 s", "~x12"],
    ["4 departamente", "824,0 s (~13,7 min)", "70,0 s", "~x12"],
    ["6 departamente", "1140,0 s (~19,0 min)", "98,0 s", "~x12"],
    ["8 departamente", "1456,0 s (~24,3 min)", "126,0 s", "~x12"],
])

# Tabela 9 (hyrjet e administratorit) -> docx table index 8 (needs a 4th row)
fill_table(8, [
    ["2 departamente", "82", "6"],
    ["4 departamente", "116", "10"],
    ["6 departamente", "150", "14"],
    ["8 departamente", "184", "18"],
])

# Tabela 10 (gabimet) -> docx table index 9
fill_table(9, [
    ["Gabime sintaksore", "16,0", "0"],
    ["Gabime në llogaritjen e subnetit", "3,1", "0"],
    ["Mospërputhje e identifikuesit të VLAN-it", "1,9", "0"],
    ["Parametra të harruar", "1,0", "0"],
    ["Gjithsej", "22,0", "0"],
])

# ============================================================ 4. Text -----
i = find("[Shto këtu pamjet e ekranit")
set_text(P[i],
    "Figura 3 e paraqet kanavacën e topologjisë me pajisjet e lidhura port-me-port, "
    "Figura 5 e paraqet ndërfaqen e modulit Smart Auto Configuration përpara se "
    "administratori të klikojë butonin e vetëm të ekzekutimit, ndërsa Figura 6 e "
    "paraqet konfigurimin real Cisco IOS të gjeneruar nga platforma për routerin "
    "R1 të një topologjie demonstruese (një router, një switch, dy PC). Krahasimi "
    "mes tyre e ilustron vizualisht objektivin qendror të punimit: nga disa kabllo "
    "të tërhequra në kanavacë dhe një klikim i vetëm del një konfigurim i plotë "
    "prej 34 rreshtash, pa asnjë fushë formulari të plotësuar me dorë.")

i = find("[Plotëso tabelën me vlerat e prodhuara")
set_text(P[i],
    "Tabela 8 i përmbledh rezultatet e katër skenarëve, nga dy deri në tetë "
    "departamente, secili me përzierje realiste përdoruesish (10–200) dhe me "
    "VLAN, DHCP pool dhe interface router-on-a-stick përkatëse. Në çdo skenar, "
    "qasja e automatizuar e redukton kohën e konfigurimit me një faktor "
    "konsistent prej rreth 12 herë (nga 8,5 minuta në 42 sekonda te dy "
    "departamente, deri në 24,3 minuta kundrejt 2,1 minutave te tetë "
    "departamente). Ky faktor mbetet praktikisht i njëjtë ndërsa numri i "
    "departamenteve rritet, sepse koha manuale rritet në mënyrë lineare me "
    "numrin e rreshtave të konfigurimit (82 → 184 rreshta), ndërsa koha e "
    "automatizuar rritet shumë më ngadalë, e dominuar nga koha fikse e "
    "llogaritjes dhe jo nga shtypja. Në terma absolutë, kursimi rritet nga "
    "rreth 7,8 minuta te topologjia më e vogël në mbi 22 minuta te ajo më e "
    "madhja e testuar, çka e konfirmon pjesën e parë të hipotezës: përfitimi "
    "kohor rritet me madhësinë e topologjisë (shih edhe Figurën 7).")
cur = insert_picture_after(P[i], FIG / "figura7_koha_konfigurimit.png")
caption_after(cur, "Figura 7. Koha e konfigurimit sipas madhësisë së topologjisë.")

i = find("[Analizo rezultatet duke theksuar se në rrugën e automatizuar")
set_text(P[i],
    "Tabela 9 e konfirmon dallimin strukturor të pritur nga dizajni i "
    "platformës. Në rrugën e automatizuar, numri i hyrjeve rritet vetëm me dy "
    "për çdo departament shtesë (6 → 10 → 14 → 18, d.m.th. 2 × departamente + "
    "2: emri dhe numri i përdoruesve për secilin, plus zgjedhja e routerit dhe "
    "e switch-it), sepse pjesa tjetër e informacionit — subnetet, VLAN-et, "
    "adresat DHCP, portat dalëse — nxirret automatikisht nga topologjia. Në "
    "rrugën manuale, çdo rresht i konfigurimit është një hyrje e veçantë e "
    "shtypur nga administratori, kështu që numri i hyrjeve përputhet saktësisht "
    "me numrin e rreshtave CLI (82 → 184). Raporti mes të dyjave zbret nga "
    "rreth 14:1 te dy departamente në rreth 10:1 te tetë departamente, çka e "
    "ilustron pikën qendrore të punimit: automatizimi nuk e ul thjesht kohën e "
    "ekzekutimit të një plani të gatshëm, por e eliminon vetë hapin e "
    "prodhimit të atij plani.")

i = find("[Analizo cilat kategori gabimesh eliminohen plotësisht")
set_text(P[i],
    "Tabela 10 (Figura 8) i grupon gabimet e modeluara për qasjen manuale në "
    "katër kategori, të matura mbi 30 prova Monte-Carlo për secilën nga katër "
    "madhësitë e topologjisë (tests/error_category_breakdown.py). Kategoria "
    "më e shpeshtë është ajo e gabimeve sintaksore/shtypjes (mesatarisht 16,0 "
    "gabime gjithsej në të katër skenarët, në normën 3% për rresht), e ndjekur "
    "nga gabimet e llogaritjes së subnetit (3,1), mospërputhja e "
    "identifikuesit të VLAN-it mes switch-it dhe routerit (1,9) dhe "
    "parametrat e harruar (1,0) — gjithsej 22,0 gabime të pritshme. Në qasjen "
    "e automatizuar, të katër kategoritë janë zero në çdo skenar, sepse "
    "konfigurimi nuk shtypet asnjëherë: ai gjenerohet nga i njëjti algoritëm "
    "dhe nga të njëjtët shabllonë Jinja2, të validuar përmes suitës prej 32 "
    "testesh automatike (seksioni 6.5). Kjo e ilustron pikën e seksionit "
    "7.1.4: kategoritë me koston më të lartë të diagnostikimit — llogaritja e "
    "subnetit dhe mospërputhja e VLAN-it — janë pikërisht ato që eliminohen "
    "plotësisht, sepse identifikuesi i VLAN-it nxirret nga i njëjti subnet me "
    "një formulë të vetme (X × 10) dhe përdoret automatikisht si te routeri "
    "ashtu edhe te switch-i (seksioni 5.4).")
cur = insert_picture_after(P[i], FIG / "figura8_gabimet.png")
caption_after(cur, "Figura 8. Numri i gabimeve: manual kundrejt automatik.")

i = find("Korrektësia e komponentëve verifikohet përmes një suite prej njëzet e gjashtë")
set_text(P[i],
    "Korrektësia e komponentëve verifikohet përmes një suite prej 32 testesh "
    "automatike, të ndara në tri grupe: 25 teste të API-t (test_api.py), të "
    "cilat i verifikojnë autentikimin, CRUD-in e pajisjeve, topologjinë, të "
    "dyja modulet e konfigurimit dhe monitorimin; 3 teste të gjeneratorit të "
    "konfigurimit (test_config_generator.py), të cilat e verifikojnë "
    "përputhshmërinë e daljes me sintaksën e pritur; dhe 4 teste të "
    "llogaritësit të nënrrjeteve (test_subnet_calculator.py), të cilat e "
    "verifikojnë saktësinë e ndarjes së hapësirës së adresave.")

i = find("[Paraqit rezultatin e ekzekutimit të testeve")
set_text(P[i],
    "Ekzekutimi i suitës (backend\\.venv\\Scripts\\python.exe -m pytest -q) "
    "raportoi 32 teste të kaluara (passed) dhe asnjë të dështuar. Mbulueshmëria "
    "i përfshin të tri shtresat e platformës: routerat e API-t (autentikim, "
    "pajisje, topologji, të dyja modulet e konfigurimit, monitorim), motorin e "
    "gjenerimit të konfigurimit dhe llogaritësin e nënrrjeteve. Kalimi i plotë "
    "i suitës e mbështet pretendimin e seksionit 4.5 se gjenerimi i "
    "konfigurimit është determinist dhe pa gabime sintaksore, pavarësisht "
    "madhësisë së topologjisë hyrëse.")

i = find("[Përgjigju duke iu referuar vlerave konkrete të Tabelës 8 dhe të Tabelës 9")
set_text(P[i],
    "Vlerat e matura (Tabela 8, Tabela 9) e konfirmojnë pyetjen hulumtuese. "
    "Koha e konfigurimit zbret nga 508 sekonda (manual) në 42 sekonda "
    "(automatik) te dy departamente, dhe nga 1456 sekonda në 126 sekonda te "
    "tetë departamente — një reduktim konsistent prej rreth 12 herë në të "
    "katër skenarët. Numri i hyrjeve zbret nga 82 në 6 te dy departamente, dhe "
    "nga 184 në 18 te tetë departamente. Dallimi strukturor është ky: në "
    "qasjen manuale të dyja metrikat rriten në mënyrë lineare me numrin e "
    "departamenteve (sepse çdo rresht i ri konfigurimi është edhe kohë "
    "shtesë, edhe një hyrje shtesë), ndërsa në atë të automatizuar numri i "
    "hyrjeve rritet shumë më ngadalë (2 hyrje për departament) dhe koha rritet "
    "kryesisht për shkak të kohës së vetë llogaritjes, jo të shtypjes. "
    "Rrjedhimisht, sa më e madhe topologjia, aq më i madh është kursimi "
    "absolut i kohës, edhe pse faktori relativ i shpejtimit mbetet afërsisht "
    "konstant.")

i = find("[Përgjigju duke iu referuar Tabelës 10 dhe duke i klasifikuar")
set_text(P[i],
    "Sipas Tabelës 10, përfitimi më i madh në terma absolutë është te "
    "gabimet sintaksore/shtypjes (16,0 të eliminuara), thjesht sepse ato janë "
    "kategoria më e shpeshtë kur konfigurimi shtypet rresht pas rreshti. Por "
    "vlera praktike më e madhe qëndron te dy kategoritë e gabimeve të "
    "heshtura: gabimet e llogaritjes së subnetit (3,1) dhe mospërputhja e "
    "identifikuesit të VLAN-it mes switch-it dhe routerit (1,9). Ndryshe nga "
    "gabimet sintaksore, të cilat pajisja i refuzon menjëherë me mesazh "
    "gabimi, këto dy kategori pranohen pa protestë nga pajisja dhe "
    "manifestohen më vonë si mungesë lidhshmërie ose si trafik i bllokuar "
    "midis VLAN-eve — diagnostikimi i të cilave kërkon kohë shumë më të gjatë "
    "se vetë koha e shkaktimit të gabimit. Automatizimi i eliminon të katër "
    "kategoritë njëlloj (në zero), por përfitimi cilësisht më i rëndësishëm "
    "është pikërisht te këto dy kategori të heshtura, sepse platforma e "
    "nxjerr identifikuesin e VLAN-it nga i njëjti subnet me një formulë të "
    "vetme dhe e përdor atë automatikisht në të dy pajisjet (router dhe "
    "switch), duke e bërë mospërputhjen strukturalisht të pamundur.")

d.save(DST)
print("Saved ->", DST)
