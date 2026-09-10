# Smart Network Automation & Configuration Management Platform — MVP

Design and implementation of a smart platform for managing, monitoring and
automating the configuration of computer networks, using **Python, FastAPI,
React, Jinja2, Netmiko and Ansible**.

This repository is the **MVP** (section 21 of the requirements): the fully
functional subset delivered for the thesis. The wider vision (RIP/BGP, ACL/NAT/STP,
backup, full security & monitoring) is documented as future work.

---

## What the MVP does

| Module | Scope |
|---|---|
| **Authentication** | Login / Logout, JWT, single `admin` role |
| **Device Management** | Add / Edit / Delete / List — Router, Switch, PC · search · SSH status check |
| **Network Topology** | React Flow canvas: drag & drop, link (access/trunk), delete, online/offline status |
| **Manual Configuration** | Hostname, Interface, IP/Mask, VLAN, DHCP — generate Cisco IOS + optional SSH deploy |
| **Smart Auto Configuration** | Input *devices + departments + user counts* → auto subnet → VLAN → IP → DHCP → OSPF → Cisco config → Ansible artifacts → optional SSH deploy → DB |
| **Dashboard** | Device counts, online/offline, VLAN count, deploy history |
| **Logging** | Configuration logs + Error logs (+ deploy/auth), filterable |
| **Testing** | `tests/compare_manual_vs_auto.py` — time & error comparison for the thesis |

Database: **7 tables** — Users, Devices, Connections, VLANs, Interfaces, Routing (OSPF), Logs.

---

## Tech stack

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy 2, SQLite, Pydantic v2, python-jose (JWT), passlib
- **Automation:** Jinja2 templates → Cisco IOS; **Netmiko** for SSH deployment (primary, works on Windows);
  generated **Ansible** inventory + playbooks per deploy (run from Linux/WSL where `ansible` is installed)
- **Frontend:** React 18 + Vite, React Router, React Flow, Axios
- **Lab:** GNS3 / Cisco Packet Tracer / EVE-NG

---

## Quick start

### 1. Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env          # optional, edit secrets
python -m uvicorn main:app --reload --port 8000
```

- API docs: http://localhost:8000/docs
- On first run the DB is created and seeded with `admin / admin123` plus demo devices (R1, SW1, PC1, PC2).

### 2. Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — the dev server proxies `/api` to `http://localhost:8000`.

### 3. Tests

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q          # unit + API tests

cd ..
backend\.venv\Scripts\python.exe tests\compare_manual_vs_auto.py   # thesis experiment
```

---

## How Smart Auto Configuration works

1. **Subnet calculator** (`services/subnet_calculator.py`) — for each department picks the
   smallest prefix that fits `users + 2`, carves consecutive, non-overlapping subnets from
   `IP_POOL_BASE` (default `10.10.0.0/16`), assigns a VLAN id (10, 20, 30, …) and a gateway
   (first usable host).
2. **Config generator** (`services/config_generator.py` + `automation/templates/*.j2`) —
   router-on-a-stick: one `dot1Q` sub-interface per VLAN, IOS DHCP pools, single-area OSPF;
   switches get the VLAN database + a trunk uplink.
3. **Deployment** (`services/deployment_service.py`) — pushes the config with Netmiko
   (`send_config_set` + `write memory`), and always writes
   `automation/generated/<host>.{cfg,inventory.yml,playbook.yml}` for the Ansible workflow.
4. **Persistence** — VLANs, interfaces and the OSPF routing row are written to SQLite; every
   step is logged.

Set `deploy: false` (the default in the UI) to generate + save without touching devices.

---

## Deploying to a real lab

1. Build a topology in GNS3 / Packet Tracer with a router + switch, enable SSH:

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

2. In the platform: **Devices → Edit** → set Management IP + SSH username/password/enable secret.
3. **Smart Auto Config** or **Manual Config** → tick **Deploy over SSH** → run.
4. To run the generated Ansible playbook instead (from Linux/WSL with `ansible` + `cisco.ios`):

   ```bash
   ansible-galaxy collection install cisco.ios
   ansible-playbook -i backend/automation/generated/R1-autoconfig-*.inventory.yml \
                    backend/automation/generated/R1-autoconfig-*.playbook.yml
   ```

---

## Project layout

```
backend/    FastAPI app — routers/ services/ automation/ models.py schemas.py
frontend/   React + Vite — components/ pages/ services/api.js context/
tests/      compare_manual_vs_auto.py (thesis experiment)
network_lab/  gns3/ topology/ test_cases/
documentation/  DatabaseDesign.md, diagrams
```

## Default credentials

`admin` / `admin123` — change via `backend/.env` before any real use.
