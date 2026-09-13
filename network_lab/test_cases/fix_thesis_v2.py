# -*- coding: utf-8 -*-
"""Second pass: v4 -> v5.

- Fixes the Kodi numbering into correct reading order (1..4), adds two more
  real code excerpts (Kodi 5, 6) from the running codebase.
- Inserts 4 more REAL screenshots (login, device management, manual
  configuration, dashboard) and renumbers all figures into one consistent
  reading-order sequence (1-12).
- Adds a short new subsection 5.9 "Konfigurimi manual" with a real screenshot.
"""
from pathlib import Path

import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.text.paragraph import Paragraph

SRC = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v4.docx")
DST = Path(r"C:\Users\armen\Downloads\Punim_Diplome_Argjend_Ejupi_v5.docx")
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


def code_block_after(ref: Paragraph, intro: str, code_lines, caption: str) -> Paragraph:
    cur = insert_para_after(ref, intro)
    for line in code_lines:
        cur = insert_para_after(cur, line, font_name="Consolas", size=9)
    return caption_after(cur, caption)


def find(substr: str) -> int:
    for i, p in enumerate(P):
        if substr in p.text:
            return i
    raise ValueError(f"not found: {substr!r}")


def find_all(substr: str) -> list:
    return [i for i, p in enumerate(P) if substr in p.text]


# ============================== 1. Kodi renumbering (1..4) + two new blocks
# Final reading order: 1=VLAN scheme (5.1, NEW), 2=subnet calc (5.4, was "1"),
# 3=router-to-router address (5.5.1, was "3" - already correct number),
# 4=Jinja2 interface fragment (5.6, was "2"). Netmiko/verification below
# become 5/6.
i1_ref = find("Kodi 1 e paraqet")
i1_cap = find("Kodi 1. Llogaritja e n\u00ebnrrjetit")
i2_ref = find("Kodi 2 e paraqet")
i2_cap = find("Kodi 2. Fragment i shabllonit Jinja2")
i3_ref = find("Kodi 3 e paraqet")
i3_cap = find("Kodi 3. Caktimi automatik i adresave")

set_text(P[i1_ref], "Kodi 2 e paraqet logjik\u00ebn baz\u00eb t\u00eb llogaritjes s\u00eb "
                     "n\u00ebnrrjetit dhe t\u00eb nxjerrjes s\u00eb adres\u00ebs s\u00eb par\u00eb t\u00eb lir\u00eb.")
set_text(P[i1_cap], "Kodi 2. Llogaritja e n\u00ebnrrjetit dhe nxjerrja e adres\u00ebs s\u00eb par\u00eb t\u00eb lir\u00eb.")

set_text(P[i3_ref], "Kodi 3 e paraqet logjik\u00ebn e caktimit t\u00eb adresave p\u00ebr "
                     "nj\u00eb lidhje pik\u00eb-me-pik\u00eb.")
set_text(P[i3_cap], "Kodi 3. Caktimi automatik i adresave p\u00ebr nj\u00eb lidhje router-me-router.")

set_text(P[i2_ref], "Kodi 4 e paraqet nj\u00eb fragment t\u00eb shabllonit q\u00eb i "
                     "gjeneron interface-t e nj\u00eb routeri.")
set_text(P[i2_cap], "Kodi 4. Fragment i shabllonit Jinja2 p\u00ebr gjenerimin e interface-ve t\u00eb routerit.")

# --- new Kodi 1: VLAN scheme, section 5.1 (must appear FIRST in reading order)
i_tabela6 = find("Tabela 6. Rolet e serverit dhe efekti i tyre")
kodi1_cap = code_block_after(
    P[i_tabela6],
    "Kodi 1 e paraqet funksionin q\u00eb e zbaton skem\u00ebn deterministike t\u00eb "
    "VLAN-eve (seksioni 5.4): identifikuesi nxirret nga vet\u00eb subneti, jo nga "
    "nj\u00eb regjist\u00ebr i ve\u00e7ant\u00eb, dhe ruhet n\u00eb nj\u00eb tabel\u00eb hash q\u00eb e "
    "garanton unicitetin global brenda t\u00eb gjith\u00eb topologjis\u00eb.",
    [
        "def _vlan_for(lan: dict) -> int:",
        "    key = f\"{lan['network']}/{lan['prefix']}\"",
        "    if key in lan_vlan_id:",
        "        return lan_vlan_id[key]",
        "    net = ipaddress.ip_network(key, strict=False)",
        "    if str(net.network_address).startswith(\"192.168.\") and net.prefixlen == 24:",
        "        vid = net.network_address.packed[2] * 10 or 10  # 192.168.X.0/24 -> X*10",
        "    else:",
        "        vid = _next_vlan_id[0]",
        "        _next_vlan_id[0] += 10",
        "    while vid in lan_vlan_id.values() or vid > 4094:",
        "        vid = (vid % 4090) + 1",
        "    lan_vlan_id[key] = vid",
        "    return vid",
    ],
    "Kodi 1. Nxjerrja deterministike e identifikuesit t\u00eb VLAN-it nga subneti.",
)
insert_para_after(
    kodi1_cap,
    "Rreshti 6 e trajton rastin e zakonsh\u00ebm (rrjet lokal 192.168.X.0/24): "
    "VLAN-i del direkt nga okteti i tret\u00eb i rrjetit, shum\u00ebzuar me 10. "
    "Rreshtat 11-12 e mbrojn\u00eb rastin e rrall\u00eb t\u00eb nj\u00eb p\u00ebrplasjeje ose t\u00eb "
    "nj\u00eb vlere jasht\u00eb diapazonit t\u00eb vlefsh\u00ebm (1-4094) t\u00eb Cisco IOS, duke "
    "e zhvendosur identifikuesin te vlera tjet\u00ebr e lir\u00eb.",
)

# ============= 2. New Kodi 5 (Netmiko dispatch, section 5.7) + Kodi 6 (5.8)
i_end57 = find("Parazgjedhja e nd\u00ebrfaqes \u00ebsht\u00eb gjenerimi pa d\u00ebrgim")
code_block_after(
    P[i_end57],
    "Kodi 5 e paraqet funksionin qendror t\u00eb rrug\u00ebs Netmiko: konfigurimi "
    "shndërrohet n\u00eb nj\u00eb list\u00eb rreshtash CLI (config_to_commands), d\u00ebrgohet "
    "brenda nj\u00eb seance SSH t\u00eb vet\u00eb dhe ruhet me write memory p\u00ebrpara se "
    "lidhja t\u00eb mbyllet.",
    [
        "def push_config(device, config: str) -> str:",
        "    if settings.deploy_dry_run:",
        "        return \"[dry-run] configuration NOT sent\"",
        "    commands = config_to_commands(config)",
        "    if not commands:",
        "        raise DeployError(\"Empty configuration.\")",
        "    conn = _connect(device)",
        "    try:",
        "        if device.ssh_secret:",
        "            conn.enable()",
        "        output = conn.send_config_set(commands, read_timeout=60)",
        "        output += \"\\n\" + conn.save_config()",
        "    finally:",
        "        conn.disconnect()",
        "    return output",
    ],
    "Kodi 5. D\u00ebrgimi i konfigurimit te pajisja reale p\u00ebrmes Netmiko.",
)

i_verif = find("M\u00ebnyra e par\u00eb \u00ebsht\u00eb verifikimi n\u00eb modalitet projektimi")
code_block_after(
    P[i_verif],
    "Kodi 6 e paraqet funksionin e brendsh\u00ebm resolve() t\u00eb verifikimit n\u00eb "
    "modalitet projektimi: nj\u00eb adres\u00eb vler\u00ebsohet e vlefshme vet\u00ebm n\u00ebse i "
    "p\u00ebrket realisht nj\u00eb pajisjeje t\u00eb caktuar n\u00eb baz\u00ebn e t\u00eb dh\u00ebnave — "
    "asnj\u00eb adres\u00eb e supozuar nuk trajtohet si e arritshme.",
    [
        "def resolve(ip: str):",
        "    try:",
        "        addr = ipaddress.ip_address(ip)",
        "    except ValueError:",
        "        return None",
        "    if str(addr) not in assigned:",
        "        return None          # asnjë pajisje nuk e mban këtë IP",
        "    info = assigned[str(addr)]",
        "    in_real = [s[\"net\"] for s in real if addr in s[\"net\"]]",
        "    if in_real:",
        "        net = max(in_real, key=lambda n: n.prefixlen)",
        "    else:",
        "        m = [s[\"net\"] for s in mgmt if addr in s[\"net\"]]",
        "        net = max(m, key=lambda n: n.prefixlen) if m else ipaddress.ip_network(f\"{addr}/32\")",
        "    return net, info[\"is_router\"]",
    ],
    "Kodi 6. Rezolucioni i nj\u00eb adrese n\u00eb modalitetin e verifikimit t\u00eb projektimit.",
)

print("Kodi blocks done.")

# ============================================================ 3. Screenshots
# --- Login screenshot -> Figura 3 (end of 5.2, before 5.3)
i = find("Qasja në platformë kërkon autentikim")
cur = insert_picture_after(P[i], FIG / "shot_login.png", width_in=3.2)
caption_after(cur, "Figura 3. Faqja e kyçjes (Sign in).")

# --- Devices screenshot -> Figura 4 (end of 5.3 intro, before the topology placeholder)
i = find("Ky vendim u mor sepse platforma duhet të jetë e përdorshme")
cur = insert_picture_after(P[i], FIG / "shot_devices.png")
caption_after(cur, "Figura 4. Menaxhimi i pajisjeve (Device Management).")

# --- replace the two red screenshot placeholders with the REAL screenshots
i = find("[FIGURA 3 - vendos këtu")
set_text(P[i], "")
cur = insert_picture_after(P[i], FIG / "shot_topology.png")
caption_after(cur, "Figura 5. Kanavaca e topologjisë me pajisjet e lidhura port-me-port.")
# remove the old caption line that followed the placeholder (now duplicate)
i_oldcap = find_all("Figura 3. Kanavaca e topologjisë me pajisjet e lidhura port-me-port.")[-1]
set_text(P[i_oldcap], "")

# Figura 4 (flow) -> Figura 6
i = find_all("Figura 4. Rrjedha e plotë e procesit Smart Auto Configuration.")[-1]
set_text(P[i], "Figura 6. Rrjedha e plotë e procesit Smart Auto Configuration.", italic=True)

# Figura 5 placeholder (Smart Auto Config UI) -> real screenshot, Figura 7
i = find("[FIGURA 5 - vendos këtu")
set_text(P[i], "")
cur = insert_picture_after(P[i], FIG / "shot_smart_config.png")
caption_after(cur, "Figura 7. Ndërfaqja e modulit Smart Auto Configuration.")
i_oldcap = find_all("Figura 5. Ndërfaqja e modulit Smart Auto Configuration.")[-1]
set_text(P[i_oldcap], "")

# Figura 6 (cisco config) -> Figura 8
i = find_all("Figura 6. Konfigurimi i gjeneruar Cisco IOS për një router.")[-1]
set_text(P[i], "Figura 8. Konfigurimi i gjeneruar Cisco IOS për një router.", italic=True)

# --- new subsection 5.9 with the Manual Configuration screenshot -> Figura 9
i = find("Ky kapitull i përshkroi rregullat e motorit të konfigurimit")
cur = insert_para_after(P[i], "5.9  Konfigurimi manual (rasti alternativ)", bold=True, size=13)
cur = insert_para_after(cur,
    "Përveç rrugës automatike, platforma e mban plotësisht funksional edhe "
    "modulin origjinal Manual Configuration, i cili u shërben dy skenarëve: "
    "rregullimeve të imëta mbi një pajisje të konfiguruar tashmë nga Smart "
    "Auto Configuration (p.sh. shtimi i një interface-i shtesë), dhe rasteve "
    "kur administratori dëshiron kontroll të plotë mbi çdo parametër. Për një "
    "router, formulari lejon deklarimin manual të interface-ve (emër, IP, "
    "maskë), pool-eve DHCP dhe, ndryshe nga versioni fillestar i platformës, "
    "edhe të OSPF-së dhe BGP-së njëkohësisht — të njëjtat protokolle që "
    "Smart Auto Configuration i vendos automatikisht. Për një switch, "
    "formulari e kufizon vetveten te parametrat e Layer 2 (VLAN, mode i "
    "portit): fusha e IP-së hiqet tërësisht nga ndërfaqja, në përputhje me "
    "rregullin e parë të motorit të konfigurimit (seksioni 5.1).")
cur = insert_picture_after(cur, FIG / "shot_manual_config.png", width_in=4.6)
caption_after(cur, "Figura 9. Ndërfaqja e modulit Manual Configuration (router me OSPF/BGP).")

# --- Dashboard screenshot -> Figura 10, in 6.1, after the (rewritten) overview
i = find("Figura 3 e paraqet kanavacën e topologjisë")
set_text(P[i],
    "Figura 3 e paraqet faqen e kyçjes, Figura 4 menaxhimin e pajisjeve dhe "
    "Figura 10 (më poshtë) dashboard-in me numërimin e pajisjeve sipas tipit "
    "dhe tabelën e adresimit të rrjetit. Figura 5 e paraqet kanavacën e "
    "topologjisë me 22 pajisje reale të lidhura port-me-port (dy routera, "
    "katër switch-a, tetë PC, katër telefona IP dhe katër printerë), Figura 7 "
    "e paraqet ndërfaqen e modulit Smart Auto Configuration përpara se "
    "administratori të klikojë butonin e vetëm të ekzekutimit, Figura 8 e "
    "paraqet konfigurimin real Cisco IOS të gjeneruar për routerin R1 të një "
    "topologjie demonstruese më të vogël, ndërsa Figura 9 e paraqet "
    "formularin e Manual Configuration për një router, me OSPF-në dhe BGP-në "
    "të dyja të aktivizueshme njëkohësisht. Krahasimi mes tyre e ilustron "
    "vizualisht objektivin qendror të punimit: nga disa kabllo të tërhequra "
    "në kanavacë dhe një klikim i vetëm del një konfigurim i plotë prej 34 "
    "rreshtash, pa asnjë fushë formulari të plotësuar me dorë.")
cur = insert_picture_after(P[i], FIG / "shot_dashboard.png")
caption_after(cur, "Figura 10. Dashboard-i me numërimin e pajisjeve dhe adresimin e rrjetit.")

# Figura 7 (koha chart) -> Figura 11
i = find_all("Figura 7. Koha e konfigurimit sipas madhësisë së topologjisë.")[-1]
set_text(P[i], "Figura 11. Koha e konfigurimit sipas madhësisë së topologjisë.", italic=True)

# "(Figura 8)" mention + Figura 8 caption (gabimet chart) -> Figura 12
i = find("Tabela 10 (Figura 8) i grupon gabimet")
set_text(P[i], P[i].text.replace("(Figura 8)", "(Figura 12)"))
i = find_all("Figura 8. Numri i gabimeve: manual kundrejt automatik.")[-1]
set_text(P[i], "Figura 12. Numri i gabimeve: manual kundrejt automatik.", italic=True)

# ================================================ 4. Lista e Figurave (front matter)
final_list = [
    "Figura 1. Arkitektura tri-shtresore e platformës dhe rrjedha e një kërkese.",
    "Figura 2. Skema relacionale e bazës së të dhënave.",
    "Figura 3. Faqja e kyçjes (Sign in).",
    "Figura 4. Menaxhimi i pajisjeve (Device Management).",
    "Figura 5. Kanavaca e topologjisë me pajisjet e lidhura port-me-port.",
    "Figura 6. Rrjedha e plotë e procesit Smart Auto Configuration.",
    "Figura 7. Ndërfaqja e modulit Smart Auto Configuration.",
    "Figura 8. Konfigurimi i gjeneruar Cisco IOS për një router.",
    "Figura 9. Ndërfaqja e modulit Manual Configuration (router me OSPF/BGP).",
    "Figura 10. Dashboard-i me numërimin e pajisjeve dhe adresimin e rrjetit.",
    "Figura 11. Koha e konfigurimit sipas madhësisë së topologjisë.",
    "Figura 12. Numri i gabimeve: manual kundrejt automatik.",
]
front_idx = find_all("Figura 1. Arkitektura tri-shtresore")
front_i = [j for j in front_idx if j < 100][0]  # the front-matter occurrence (near the top)
front_indices = list(range(front_i, front_i + 8))
for idx, text in zip(front_indices, final_list[:8]):
    set_text(P[idx], text)
cur = P[front_indices[-1]]
for text in final_list[8:]:
    cur = insert_para_after(cur, text)

d.save(DST)
print("Final saved ->", DST)
