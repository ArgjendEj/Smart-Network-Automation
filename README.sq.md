# Platformë për Automatizimin dhe Menaxhimin e Konfigurimit të Rrjetit — MVP

[🇬🇧 English](README.md) · **🇦🇱 Shqip**

Një platformë web që **menaxhon një topologji rrjeti Cisco, gjeneron
automatikisht konfigurimin Cisco IOS dhe e dërgon atë përmes SSH** — e ndërtuar
për temën e masterit me **Python / FastAPI, React, Jinja2, Netmiko dhe Ansible**.

Ky depo është **MVP** (seksioni 21 i kërkesave): nënbashkësia plotësisht
funksionale e dorëzuar për temën. Vizioni më i gjerë (ACL i plotë, STP, backup/
restore i konfigurimit, monitorim dhe siguri të avancuar) është dokumentuar si
punë e ardhshme.

---

## Përmbajtja

1. [Çfarë bën](#1-çfarë-bën)
2. [Vendimet kryesore të dizajnit](#2-vendimet-kryesore-të-dizajnit)
3. [Si funksionon (një URL)](#3-si-funksionon-një-url)
4. [Teknologjitë](#4-teknologjitë)
5. [Nisja e shpejtë](#5-nisja-e-shpejtë)
6. [Smart Auto Configuration](#6-smart-auto-configuration)
7. [Manual Configuration](#7-manual-configuration)
8. [Testimi i lidhshmërisë / ping](#8-testimi-i-lidhshmërisë--ping)
9. [Dërgimi në një lab real](#9-dërgimi-në-një-lab-real)
10. [Testet dhe eksperimenti i temës](#10-testet-dhe-eksperimenti-i-temës)
11. [Skema e bazës së të dhënave](#11-skema-e-bazës-së-të-dhënave)
12. [Struktura e projektit](#12-struktura-e-projektit)

---

## 1. Çfarë bën

| Moduli | Përfshirja |
|---|---|
| **Autentikimi** | Kyçje / **Regjistrim** (vetë-regjistrim, hapet vetëm nga faqja e kyçjes) / dalje · JWT · roli `admin` · buton shfaq/fsheh fjalëkalimin |
| **Menaxhimi i pajisjeve** | Shto / ndrysho / fshi / listo · 6 tipe pajisjesh (Router, Switch, PC, IP Phone, Printer, Server) · vendosje IP-je për çdo interface · rolet e serverit · kontroll i arritshmërisë me SSH (edhe switch-i mund të mbajë kredenciale SSH, pa IP) |
| **Topologjia e rrjetit** | Kanavacë React Flow: tërhiq-dhe-lësho, lidh pajisjet port-me-port (kablloja del automatikisht nga ana që sheh pajisjen tjetër), fshi lidhjet, statusi online/offline në kohë reale, IP me ngjyra (jeshile = LAN/menaxhim, portokalli = router-me-router, kaltër = adresa e vet endpoint-it) |
| **Smart Auto Configuration** | Një klik, pa formularë: lexon topologjinë dhe gjeneron subnet-e → VLAN-e → gateway-t → DHCP → routing (OSPF / BGP / të dyja) → NAT opsional → Cisco IOS → artefakte Ansible → dërgim opsional me SSH → DB |
| **Manual Configuration** | Vetëm router/switch: hostname, interfaces, IP/maskë, VLAN (vetëm switch), DHCP pools, **OSPF**, **BGP** → Cisco IOS + dërgim opsional me SSH |
| **Dashboard** | Numri i pajisjeve sipas tipit, online/offline, numri i VLAN-eve, dërgimet e fundit |
| **Logging** | Log-e për konfigurim / deploy / autentikim / sistem, me filtra |
| **Eksperimenti i temës** | `tests/compare_manual_vs_auto.py` — koha, hyrjet e administratorit dhe gabimet: CLI manual kundrejt platformës |

Të dhëna fillestare në nisjen e parë: `admin / admin123` + pajisjet demo
**R1, SW1, PC1, PC2**.

---

## 2. Vendimet kryesore të dizajnit

Këto janë rregullat që ndjek motori i konfigurimit (të ndërtuara gjatë punës në
temë):

**Pajisjet**
- Një **switch është Layer 2 i pastër** — nuk merr kurrë IP apo IP menaxhimi.
  Mund të mbajë kredencialet SSH që konfigurimi i gjeneruar të shfaqë bllokun e
  menaxhimit SSH (`username`, `line vty`, `transport input ssh`, `login local`) —
  pa iu shtuar asnjë IP.
- **PC / IP Phone / Printer / Server** janë endpoint-e. PC-ja, telefoni dhe
  printeri e marrin adresën me DHCP; një **server mban një adresë statike të
  ulët** dhe rolet e tij futen në konfigurimin e routerit.
- **Rolet e serverit** (`DHCP, DNS, Web, Syslog, NTP, Monitoring`) ushqejnë
  konfigurimin e routerit: DNS → `dns-server`, Syslog → `logging host`,
  NTP → `ntp server`, DHCP → routeri bëhet relay (`ip helper-address`) në vend që
  ta mbajë vetë pool-in.
- Një pajisje shfaqet **online** sapo lidhet në topologji.
- Portat fizike të një routeri janë të gjitha **GigabitEthernet0/0 – 0/5** (6
  gjithsej, 3 lart / 3 poshtë në nyjen e topologjisë) — pa porta Serial.

**Adresimi**
- **Rrjetet lokale** përdorin Class C — `192.168.1.0/24 … 192.168.255.0/24`.
- **Lidhjet router-me-router** përdorin Class A — `10.0.0.0/8`, gjithmonë një
  **/30 (255.255.255.252)**, `.1` / `.2`. Një router mund të ketë **disa lidhje
  me të njëjtin router tjetër** (redundante / për ndarje ngarkese) — secila
  merr interface-in dhe /30-ën e vet, dhe rifillimi nuk i bashkon apo lëviz kurrë.
- Nëse administratori ka shtypur një IP menaxhimi te routeri, ajo IP mbahet si
  **gateway i LAN-it**; një IP `10.x` e shtypur përdoret e njëjtë në lidhjen
  router-me-router (peer-i merr adresën tjetër të /30-ës).
- Një router mund të mbajë **disa gateway LAN të shkruara me dorë** njëherësh
  (`Devices → Edit → Interface IP addresses`) — çdo switch i lidhur me të merr
  radhazi IP-në tjetër të papërdorur; të tjerat presin pa u fshirë për switch-in
  tjetër.
- Çdo PC/telefon/printer/server i bashkohet segmentit të **switch-it më të
  afërt që ka lidhje me routerin**, edhe kur dy switch-a të lidhur me router
  janë të lidhur edhe me njëri-tjetrin (një lak L2) — kështu një pajisje nuk
  përfundon kurrë në subnet-in e gabuar vetëm sepse switch-i i saj ka edhe një
  rrugë tjetër drejt routerit.
- **DHCP-ja është sekuenciale dhe e qëndrueshme**: PC-të marrin `.2, .3, .4 …`
  sipas radhës së hostname-it; rifillimi pas ndryshimit të IP-së i rinumëron
  pastër pa lënë adresa të vjetra.
- **Skema e VLAN id-ve**: `192.168.X.0/24` → VLAN `X × 10` (deterministike,
  globalisht unike në gjithë topologjinë), që id-ja të përputhet te routeri, te
  switch-i dhe te DHCP.
- Kabllot e mbetura/të dyfishta (nga rilidhja e pajisjeve) pastrohen
  automatikisht — përveç një lidhjeje të dytë të vërtetë mes dy routerash, që
  nuk trajtohet kurrë si e dyfishtë.

**Konfigurimi**
- **VLAN-et janë vetëm te switch-i** — konfigurimi i routerit nuk nxjerr kurrë
  komanda `vlan` apo `switchport`.
- **Opsionet e routing-ut**: OSPF (area 0 e vetme, interface-t LAN passive),
  eBGP (një AS privat për çdo router, `65000 + id`), ose **të dyja njëherësh**.
- **NAT overload (PAT)** është opsional dhe **vetëm për router**: LAN-et = inside,
  lidhja e parë router-me-router = outside.
- Template-t renderohen me Jinja2 (`trim_blocks`, `lstrip_blocks`,
  `StrictUndefined`); një pastrues heq rreshtat bosh të tepërt.

**Dërgimi (deploy)**
- **Netmiko / SSH është rruga kryesore e dërgimit** (funksionon në Windows).
- **Ansible** inventory + playbook (`cisco.ios.ios_config`) shkruhen për çdo
  dërgim, që workflow-i të mund të demonstrohet / ekzekutohet nga Linux/WSL.
- `deploy: false` (parazgjedhja në UI) gjeneron dhe ruan konfigurimin pa prekur
  asnjë pajisje.

---

## 3. Si funksionon (një URL)

Serveri FastAPI shërben edhe aplikacionin React të ndërtuar, kështu që e gjithë
platforma është një URL e vetme e menjëhershme — **http://localhost:8000** — pa
server development që duhet mbajtur hapur.

```
browser ──► http://localhost:8000
              │
              ├── /              → React SPA (frontend/dist)
              └── /api/*         → FastAPI (auth, devices, topology,
                                   smart-config, manual-config, monitoring, logs)
                                        │
                                        ├── SQLite (backend/database/network.db)
                                        ├── Jinja2 → Cisco IOS
                                        ├── Netmiko → SSH te routerat
                                        └── automation/generated/*.{cfg,yml}
```

Në Windows, `start.bat` e ndërton frontend-in një herë, e nis serverin fshehtas
(`server.vbs`) dhe hap browserin. `stop.bat` e ndal.

---

## 4. Teknologjitë

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy 2, SQLite, Pydantic v2,
  python-jose (JWT), passlib (`pbkdf2_sha256`)
- **Automatizim:** Jinja2 → Cisco IOS · **Netmiko** për SSH · **Ansible**
  inventory + playbook të gjeneruar
- **Frontend:** React 18 + Vite, React Router, React Flow, Axios
- **Lab:** Cisco Packet Tracer / GNS3 / EVE-NG (ose kontrolli i integruar i
  arritshmërisë në design-mode — pa lab)

---

## 5. Nisja e shpejtë

### Windows (një klik)

```
kliko dy herë start.bat     →  ndërton një herë, nis serverin, hap http://localhost:8000
kliko dy herë stop.bat      →  ndal serverin
```

### Manual / development

**Backend**

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env          # opsionale, ndrysho sekretet
python -m uvicorn main:app --reload --port 8000
```

Dokumentimi i API-t: http://localhost:8000/docs

**Frontend**

```powershell
cd frontend
npm install
npm run dev      # http://localhost:5173, e kalon /api te :8000
# ose:
npm run build    # output-i shërbehet nga backend-i te http://localhost:8000
```

---

## 6. Smart Auto Configuration

**Devices → Topology**: vendos pajisjet, lidhi ato. **Smart Auto Config**: zgjidh
një protokoll routing-u (OSPF / BGP / të dyja), opsionalisht cek NAT, pastaj
kliko një nga butonat:

| Butoni | Fusha | Rezultati |
|---|---|---|
| 🏠 **Configure local networks + DHCP** | `lan` | çdo lidhje router↔switch/PC merr një `192.168.x.0/24`, një DHCP pool, një VLAN; çdo PC/telefon/printer merr adresë; serverat mbajnë një adresë statike; çdo switch merr VLAN-in e vet |
| 🔗 **Configure router-to-router links** | `wan` | çdo lidhje router↔router merr një `/30` përputhës nga `10.0.0.0/8` + routing-un e zgjedhur |
| **Both** | `all` | LAN + WAN së bashku |

Pipeline-i (`services/auto_topology_service.py`):

1. **Lexon grafin** — rreshtat `Connection` → kush është i lidhur me kë.
2. **Cakton adresimin** — LAN `/24` për segment (duke respektuar një IP menaxhimi
   të shtypur), WAN `/30` për çdo lidhje routeri, VLAN id-e deterministike, DHCP
   sekuenciale.
3. **Gjeneron** — `config_generator.py` + `automation/templates/router_auto.j2`
   / `switch_auto.j2`: interface-t LAN + DHCP (ose relay), interface-t WAN `/30`,
   OSPF / BGP, NAT opsional, rreshtat e roleve të serverit (DNS / Syslog / NTP).
4. **Ruan dhe dërgon** — rreshtat VLAN / Interface / Routing te SQLite; dërgim me
   Netmiko nëse kërkohet; artefaktet Ansible shkruhen gjithmonë; çdo hap logohet.

---

## 7. Manual Configuration

Vetëm router ose switch. Formulari përshtatet sipas tipit:

- **Switch** — vetëm Layer 2: interfaces (mode/VLAN, pa IP), një bazë VLAN-esh,
  pa DHCP, pa routing.
- **Router** — interfaces me IP/maskë, DHCP pools, **OSPF** (process id,
  router-id, deklaratat `network`), **BGP** (numri AS, rrjetet e reklamuara,
  fqinjët). Nuk nxirret kurrë asnjë komandë VLAN / switchport.

Gjeneron Cisco IOS, e ruan, opsionalisht e dërgon përmes SSH.

---

## 8. Testimi i lidhshmërisë / ping

`POST /api/monitoring/ping` — tri mënyra:

- **design** *(pa lab)* — verifikon arritshmërinë nga topologjia + plani i IP-ve:
  i njëjti subnet → direkt; subnet-e të ndryshme → duhet të kalojë përmes
  routerit; një IP që nuk e ka askush nuk është kurrë "e suksesshme".
- **server** — një ping real ICMP nga hosti ku po ekzekutohet platforma.
- **device** — SSH në një router dhe ekzekuton `ping` atje.

`GET /api/monitoring/endpoints` liston çdo IP të caktuar realisht në dizajn —
burimet/destinacionet e vetme të vlefshme për ping.

---

## 9. Dërgimi në një lab real

1. Ndërto një topologji me një router + switch dhe aktivizo SSH në router:

   ```
   hostname R1
   ip domain-name lab.local
   crypto key generate rsa modulus 1024
   username admin privilege 15 secret cisco
   enable secret cisco
   line vty 0 4
    transport input ssh
    login local
   interface g0/0
    ip address 192.168.10.2 255.255.255.0
    no shutdown
   ```

2. **Devices → Edit** te routeri → vendos Management IP + SSH username /
   password / enable secret.
3. **Smart Auto Config** ose **Manual Config** → cek **Deploy over SSH** →
   ekzekuto.
4. Për të ekzekutuar playbook-un **Ansible** të gjeneruar (Linux/WSL me `ansible`
   + `cisco.ios`):

   ```bash
   ansible-galaxy collection install cisco.ios
   ansible-playbook -i backend/automation/generated/R1-*-*.inventory.yml \
                    backend/automation/generated/R1-*-*.playbook.yml
   ```

---

## 10. Testet dhe eksperimenti i temës

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q        # teste unit + API (32)

cd ..
backend\.venv\Scripts\python.exe tests\compare_manual_vs_auto.py
```

Skripti i krahasimit ekzekuton disa madhësi rrjeti dhe raporton **kohën e
konfigurimit, hyrjet e administratorit dhe gabimet** për CLI manual kundrejt
platformës, duke shkruar `network_lab/test_cases/comparison_results.{csv,md}`.
Numrat AUTO maten nga pipeline-i real; MANUAL është një model vlerësimi i
dokumentuar (shpejtësia e shtypjes, matematika VLSM, shkalla e gabimit njerëzor
për rresht).

---

## 11. Skema e bazës së të dhënave

**7 tabela** (SQLite, `backend/database/network.db`):

| Tabela | Përmban |
|---|---|
| `users` | username, fjalëkalim i hashuar, roli |
| `devices` | emri, hostname, tipi, `services` i serverit, mgmt IP + kredenciale SSH, pozicioni në kanavacë, statusi, konfigurimi i fundit |
| `connections` | endpoint-et e lidhur (pajisja + interface në të dyja anët), tipi i lidhjes |
| `vlans` | vlan id, emri, subnet, gateway për pajisje |
| `interfaces` | emri, IP/maskë, mode, access VLAN, përshkrimi, enabled |
| `routing` | protokolli (ospf/bgp), process id / AS, area, networks (JSON) |
| `logs` | timestamp, niveli, kategoria, mesazhi, detajet |

Baza migron vetë në nisje (`PRAGMA table_info` + `ALTER TABLE ADD COLUMN`).

---

## 12. Struktura e projektit

```
start.bat / stop.bat / server.vbs   Nisës një-klik për Windows

backend/
  main.py                 App-i FastAPI + shërben frontend/dist
  config.py  database.py  models.py  schemas.py  seed.py  auth_utils.py
  routers/                auth, devices, topology, smart_configuration,
                          manual_configuration, monitoring, dashboard, logs
  services/               auto_topology_service, smart_config_service,
                          manual_config_service, config_generator,
                          dhcp_service, deployment_service, monitoring_service,
                          subnet_calculator, device_service, topology_service,
                          logging_service
  automation/
    templates/*.j2        router_auto, switch_auto, router_stick, interface,
                          vlan, dhcp, ospf, routing_manual
    playbooks/  inventory/  generated/
  tests/                  test_api.py, test_config_generator.py,
                          test_subnet_calculator.py

frontend/
  src/pages/              Login, Register, Dashboard, Topology, Devices,
                          SmartConfiguration, ManualConfiguration, Logs
  src/components/         DeviceForm, DeviceTable, DeviceNode, PingTest,
                          PasswordInput, …
  src/context/AuthContext.jsx    src/services/api.js

tests/compare_manual_vs_auto.py   eksperimenti i temës
network_lab/                       gns3/  topology/  test_cases/
documentation/DatabaseDesign.md
```

---

## Kredencialet e parazgjedhura

`admin` / `admin123` — ose krijo llogarinë tënde nga faqja **Regjistrohu**.
Ndrysho parazgjedhjen përmes `backend/.env` para çdo përdorimi real.
