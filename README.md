# Smart Network Automation & Configuration Management Platform — MVP

**🇬🇧 English** · [🇦🇱 Shqip](README.sq.md)

A web platform that **manages a Cisco network topology, generates Cisco IOS
configuration automatically, and deploys it over SSH** — built for the master's
thesis with **Python / FastAPI, React, Jinja2, Netmiko and Ansible**.

This repository is the **MVP** (section 21 of the requirements): the fully
functional subset delivered for the thesis. The wider vision (full ACL, STP,
config backup/restore, advanced monitoring & security) is documented as future
work.

---

## Table of contents

1. [What it does](#1-what-it-does)
2. [Key design decisions](#2-key-design-decisions)
3. [How it runs (one URL)](#3-how-it-runs-one-url)
4. [Tech stack](#4-tech-stack)
5. [Quick start](#5-quick-start)
6. [Smart Auto Configuration](#6-smart-auto-configuration)
7. [Manual Configuration](#7-manual-configuration)
8. [Reachability / ping testing](#8-reachability--ping-testing)
9. [Deploying to a real lab](#9-deploying-to-a-real-lab)
10. [Testing & the thesis experiment](#10-testing--the-thesis-experiment)
11. [Database schema](#11-database-schema)
12. [Project layout](#12-project-layout)

---

## 1. What it does

| Module | Scope |
|---|---|
| **Authentication** | Sign in / **Sign up** (self-registration, only reachable from the sign-in page) / logout · JWT · `admin` role · show/hide-password toggle |
| **Device Management** | Add / edit / delete / list · 6 device types (Router, Switch, PC, IP Phone, Printer, Server) · per-interface IP entry · server roles · SSH reachability check |
| **Network Topology** | React Flow canvas: drag & drop, cable devices port-to-port (a cable auto-routes to whichever side faces the other device), delete links, live online/offline status, colour-coded IPs (green = LAN/management, orange = router-to-router, blue = an endpoint's own address) |
| **Smart Auto Configuration** | One click, no forms: reads the topology and generates subnets → VLANs → gateways → DHCP → routing (OSPF / BGP / both) → optional NAT → Cisco IOS → Ansible artifacts → optional SSH deploy → DB |
| **Manual Configuration** | Router/switch only: hostname, interfaces, IP/mask, VLANs (switch only), DHCP pools, **OSPF**, **BGP** → Cisco IOS + optional SSH deploy |
| **Dashboard** | Device counts by type, online/offline, VLAN count, recent deploys |
| **Logging** | Config / deploy / auth / system logs, filterable |
| **Thesis experiment** | `tests/compare_manual_vs_auto.py` — time, admin inputs and errors: manual CLI vs. the platform |

Seed data on first run: `admin / admin123` + demo devices **R1, SW1, PC1, PC2**.

---

## 2. Key design decisions

These are the rules the configuration engine follows (built up over the thesis
work):

**Devices**
- A **switch is pure Layer 2** — it never receives an IP or management IP. It may
  keep SSH credentials so the generated config shows the SSH management block
  (`username`, `line vty`, `transport input ssh`, `login local`) — no IP is added.
- **PC / IP Phone / Printer / Server** are endpoints. PC, phone and printer get
  their address by DHCP; a **server keeps a static low address** and its roles
  are wired into the router.
- **Server roles** (`DHCP, DNS, Web, Syslog, NTP, Monitoring`) feed the router
  config: DNS → `dns-server`, Syslog → `logging host`, NTP → `ntp server`,
  DHCP → the router becomes a relay (`ip helper-address`) instead of hosting the
  pool.
- A device shows **online** as soon as it is cabled in the topology.
- A router's physical ports are all **GigabitEthernet0/0 – 0/5** (6 in total,
  3 drawn on top / 3 on the bottom of the topology node) — no Serial ports.

**Addressing**
- **Local networks** use Class C — `192.168.1.0/24 … 192.168.255.0/24`.
- **Router-to-router links** use Class A — `10.0.0.0/8`, always a **/30
  (255.255.255.252)**, `.1` / `.2`. A router can have **several links to the
  same peer router** (redundant / load-sharing) — each gets its own interface
  and its own /30, and re-running never merges or moves them.
- If the admin typed a Management IP on a router, that IP is kept as the **LAN
  gateway**; a typed `10.x` IP is used verbatim on the router-to-router link
  (peer takes the other /30 address).
- A router can carry **several hand-typed LAN gateways** at once (`Devices →
  Edit → Interface IP addresses`) — each switch cabled to it consumes the next
  unused one, in order; the rest wait untouched for the next switch instead of
  being deleted.
- Every PC/phone/printer/server joins the segment of the **nearest switch that
  has a router uplink**, even when two uplinked switches are also cabled to
  each other (an L2 loop) — so a host never ends up on the wrong subnet just
  because its switch has a second path back to the router.
- **DHCP is sequential and stable**: PCs get `.2, .3, .4 …` in hostname order;
  re-running after an IP change re-numbers cleanly with no stale leases.
- **VLAN id scheme**: `192.168.X.0/24` → VLAN `X × 10` (deterministic, globally
  unique across the whole topology), so the id matches on the router, the switch
  and DHCP.
- Stray/duplicate cables (leftovers from re-cabling) are cleaned up
  automatically — except a genuine second link between two routers, which is
  never treated as a duplicate.

**Configuration**
- **VLANs live only on the switch** — the router config never emits `vlan` or
  `switchport` commands.
- **Routing options**: OSPF (single area 0, passive LAN interfaces), eBGP (one
  private AS per router, `65000 + id`), or **both at once**.
- **NAT overload (PAT)** is optional and **router-only**: LANs = inside, first
  router-to-router link = outside.
- Templates render with Jinja2 (`trim_blocks`, `lstrip_blocks`,
  `StrictUndefined`); a cleaner collapses stray blank lines.

**Deployment**
- **Netmiko / SSH is the primary deploy path** (works on Windows).
- **Ansible** inventory + playbook (`cisco.ios.ios_config`) are written for every
  deploy so the workflow can be demonstrated / run from Linux/WSL.
- `deploy: false` (the UI default) generates and saves the config without
  touching any device.

---

## 3. How it runs (one URL)

The FastAPI server also serves the built React app, so the whole platform is a
single instant URL — **http://localhost:8000** — with no dev server to keep open.

```
browser ──► http://localhost:8000
              │
              ├── /              → React SPA (frontend/dist)
              └── /api/*         → FastAPI (auth, devices, topology,
                                   smart-config, manual-config, monitoring, logs)
                                        │
                                        ├── SQLite (backend/database/network.db)
                                        ├── Jinja2 → Cisco IOS
                                        ├── Netmiko → SSH to routers
                                        └── automation/generated/*.{cfg,yml}
```

On Windows, `start.bat` builds the frontend once, starts the server hidden
(`server.vbs`) and opens the browser. `stop.bat` stops it.

---

## 4. Tech stack

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy 2, SQLite, Pydantic v2,
  python-jose (JWT), passlib (`pbkdf2_sha256`)
- **Automation:** Jinja2 → Cisco IOS · **Netmiko** for SSH · generated
  **Ansible** inventory + playbooks
- **Frontend:** React 18 + Vite, React Router, React Flow, Axios
- **Lab:** Cisco Packet Tracer / GNS3 / EVE-NG (or the built-in design-mode
  reachability check — no lab required)

---

## 5. Quick start

### Windows (one click)

```
double-click start.bat      →  builds once, starts the server, opens http://localhost:8000
double-click stop.bat       →  stops the server
```

### Manual / development

**Backend**

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env          # optional, edit secrets
python -m uvicorn main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

**Frontend**

```powershell
cd frontend
npm install
npm run dev      # http://localhost:5173, proxies /api to :8000
# or:
npm run build    # output served by the backend at http://localhost:8000
```

---

## 6. Smart Auto Configuration

**Devices → Topology**: place devices, cable them. **Smart Auto Config**: pick a
routing protocol (OSPF / BGP / both), optionally tick NAT, then press one of:

| Button | Scope | Result |
|---|---|---|
| 🏠 **Configure local networks + DHCP** | `lan` | each router↔switch/PC link gets a `192.168.x.0/24`, a DHCP pool, a VLAN; every PC/phone/printer gets an address; servers keep a static one; each switch gets its VLAN |
| 🔗 **Configure router-to-router links** | `wan` | each router↔router link gets a matching `/30` from `10.0.0.0/8` + the chosen routing |
| **Both** | `all` | LAN + WAN together |

Pipeline (`services/auto_topology_service.py`):

1. **Read the graph** — `Connection` rows → who is wired to whom.
2. **Assign addressing** — LAN `/24` per segment (respecting a typed Management
   IP), WAN `/30` per router link, deterministic VLAN ids, sequential DHCP.
3. **Generate** — `config_generator.py` + `automation/templates/router_auto.j2`
   / `switch_auto.j2`: LAN interfaces + DHCP (or relay), WAN `/30` interfaces,
   OSPF / BGP, optional NAT, server-role lines (DNS / Syslog / NTP).
4. **Persist & deploy** — VLAN / Interface / Routing rows to SQLite; Netmiko
   push if requested; Ansible artifacts always written; every step logged.

---

## 7. Manual Configuration

Router or switch only. The form adapts to the type:

- **Switch** — Layer 2 only: interfaces (mode/VLAN, no IP), a VLAN database, no
  DHCP, no routing.
- **Router** — interfaces with IP/mask, DHCP pools, **OSPF** (process id,
  router-id, `network` statements), **BGP** (AS number, advertised networks,
  neighbours). No VLAN / switchport commands are ever emitted.

Generates Cisco IOS, saves it, optionally deploys over SSH.

---

## 8. Reachability / ping testing

`POST /api/monitoring/ping` — three modes:

- **design** *(no lab needed)* — validates reachability from the topology + IP
  plan: same subnet → direct; different subnets → must be routed; an IP nobody
  owns is never "successful".
- **server** — a real ICMP ping from the host running the platform.
- **device** — SSH into a router and run `ping` there.

`GET /api/monitoring/endpoints` lists every IP actually assigned in the design —
the only valid ping sources/targets.

---

## 9. Deploying to a real lab

1. Build a topology with a router + switch and enable SSH on the router:

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

2. **Devices → Edit** the router → set Management IP + SSH username / password /
   enable secret.
3. **Smart Auto Config** or **Manual Config** → tick **Deploy over SSH** → run.
4. To run the generated **Ansible** playbook instead (Linux/WSL with `ansible` +
   `cisco.ios`):

   ```bash
   ansible-galaxy collection install cisco.ios
   ansible-playbook -i backend/automation/generated/R1-*-*.inventory.yml \
                    backend/automation/generated/R1-*-*.playbook.yml
   ```

---

## 10. Testing & the thesis experiment

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q        # unit + API tests (32)

cd ..
backend\.venv\Scripts\python.exe tests\compare_manual_vs_auto.py
```

The comparison script runs several network sizes and reports **configuration
time, admin inputs and errors** for manual CLI vs. the platform, writing
`network_lab/test_cases/comparison_results.{csv,md}`. AUTO numbers are measured
from the real pipeline; MANUAL is a documented estimation model (typing speed,
VLSM math, per-line human error rate).

---

## 11. Database schema

**7 tables** (SQLite, `backend/database/network.db`):

| Table | Holds |
|---|---|
| `users` | username, hashed password, role |
| `devices` | name, hostname, type, server `services`, mgmt IP + SSH creds, canvas position, status, last config |
| `connections` | cabled endpoints (device + interface on both sides), link type |
| `vlans` | vlan id, name, subnet, gateway per device |
| `interfaces` | name, IP/mask, mode, access VLAN, description, enabled |
| `routing` | protocol (ospf/bgp), process id / AS, area, networks (JSON) |
| `logs` | timestamp, level, category, message, detail |

The DB self-migrates on startup (`PRAGMA table_info` + `ALTER TABLE ADD COLUMN`).

---

## 12. Project layout

```
start.bat / stop.bat / server.vbs   Windows one-click launcher

backend/
  main.py                 FastAPI app + serves frontend/dist
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

tests/compare_manual_vs_auto.py   thesis experiment
network_lab/                       gns3/  topology/  test_cases/
documentation/DatabaseDesign.md
```

---

## Default credentials

`admin` / `admin123` — or create your own account from the **Sign up** page.
Change the default via `backend/.env` before any real use.
