import ipaddress
import os
import tempfile

import pytest

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mktemp(suffix='.db')}"

from fastapi.testclient import TestClient  # noqa: E402

from database import init_db  # noqa: E402
from main import app  # noqa: E402
from seed import seed  # noqa: E402

init_db()
seed()
client = TestClient(app)


def _token():
    r = client.post("/api/auth/login", data={"username": "admin", "password": "admin123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth():
    return {"Authorization": f"Bearer {_token()}"}


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_login_required():
    assert client.get("/api/devices").status_code == 401


def test_register_new_account_then_login():
    r = client.post("/api/auth/register", json={"username": "thesis", "password": "secret1"})
    assert r.status_code == 201, r.text
    tok = r.json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert me.status_code == 200 and me.json()["username"] == "thesis"

    # same username is rejected
    dup = client.post("/api/auth/register", json={"username": "thesis", "password": "another1"})
    assert dup.status_code == 409

    # too-short password is rejected
    bad = client.post("/api/auth/register", json={"username": "someone", "password": "x"})
    assert bad.status_code == 422

    # the new account can log in
    li = client.post("/api/auth/login", data={"username": "thesis", "password": "secret1"})
    assert li.status_code == 200


def test_device_crud_and_dashboard():
    h = _auth()
    r = client.post("/api/devices", json={"name": "R9", "hostname": "R9", "device_type": "router"}, headers=h)
    assert r.status_code == 201
    did = r.json()["id"]

    r = client.put(f"/api/devices/{did}", json={"hostname": "R9-edit"}, headers=h)
    assert r.json()["hostname"] == "R9-edit"

    assert client.get("/api/dashboard", headers=h).json()["total_devices"] >= 1
    assert client.delete(f"/api/devices/{did}", headers=h).status_code == 204


def test_smart_config_preview_and_run():
    h = _auth()
    devices = client.get("/api/devices", headers=h).json()
    router = next(d for d in devices if d["device_type"] == "router")
    switch = next(d for d in devices if d["device_type"] == "switch")

    payload = {
        "router_id": router["id"],
        "switch_ids": [switch["id"]],
        "departments": [{"name": "Sales", "users": 100}, {"name": "IT", "users": 20}],
        "routing_protocol": "ospf",
        "enable_dhcp": True,
        "deploy": False,
    }
    prev = client.post("/api/smart-config/preview", json=payload, headers=h)
    assert prev.status_code == 200
    assert len(prev.json()["departments"]) == 2

    run = client.post("/api/smart-config/run", json=payload, headers=h)
    assert run.status_code == 200, run.text
    body = run.json()
    assert len(body["results"]) == 2
    assert "router ospf 1" in body["results"][0]["config"]
    assert body["results"][0]["deployed"] is False


def test_manual_config_run():
    h = _auth()
    switch = next(d for d in client.get("/api/devices", headers=h).json() if d["device_type"] == "switch")
    payload = {
        "device_id": switch["id"],
        "hostname": "SW1",
        "vlans": [{"vlan_id": 30, "name": "HR"}],
        "interfaces": [{"name": "GigabitEthernet0/2", "mode": "access", "vlan_id": 30}],
        "dhcp": [],
        "deploy": False,
    }
    r = client.post("/api/manual-config/run", json=payload, headers=h)
    assert r.status_code == 200, r.text
    assert "switchport access vlan 30" in r.json()["config"]


def test_manual_config_ospf_and_bgp_on_router():
    h = _auth()
    router = next(d for d in client.get("/api/devices", headers=h).json() if d["device_type"] == "router")
    payload = {
        "device_id": router["id"],
        "interfaces": [{"name": "GigabitEthernet0/1", "ip_address": "192.168.1.1", "subnet_mask": "255.255.255.0"}],
        "ospf": {
            "process_id": 1,
            "router_id": "1.1.1.1",
            "networks": [{"network": "192.168.1.0", "wildcard": "0.0.0.255", "area": "0"}],
        },
        "bgp": {
            "asn": 65001,
            "networks": [{"network": "192.168.1.0", "mask": "255.255.255.0"}],
            "neighbors": [{"ip": "10.0.0.2", "remote_as": 65002}],
        },
        "deploy": False,
    }
    r = client.post("/api/manual-config/run", json=payload, headers=h)
    assert r.status_code == 200, r.text
    cfg = r.json()["config"]
    assert "router ospf 1" in cfg
    assert "network 192.168.1.0 0.0.0.255 area 0" in cfg
    assert "router bgp 65001" in cfg
    assert "neighbor 10.0.0.2 remote-as 65002" in cfg


def test_manual_config_router_never_gets_vlan_commands():
    h = _auth()
    router = next(d for d in client.get("/api/devices", headers=h).json() if d["device_type"] == "router")
    payload = {
        "device_id": router["id"],
        "vlans": [{"vlan_id": 40, "name": "SALES"}],
        "interfaces": [{"name": "GigabitEthernet0/2", "mode": "access", "vlan_id": 40}],
        "deploy": False,
    }
    r = client.post("/api/manual-config/run", json=payload, headers=h)
    assert r.status_code == 200, r.text
    cfg = r.json()["config"]
    assert "vlan 40" not in cfg
    assert "switchport" not in cfg


def test_monitoring_ping_from_server():
    h = _auth()
    r = client.post(
        "/api/monitoring/ping",
        json={"mode": "server", "target": "127.0.0.1", "count": 1},
        headers=h,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source"] == "server"
    assert body["ok"] is True
    assert body["loss_pct"] == 0


def test_monitoring_simulated_reachability():
    h = _auth()
    devices = client.get("/api/devices", headers=h).json()
    router = next(d for d in devices if d["device_type"] == "router")
    switch = next(d for d in devices if d["device_type"] == "switch")
    res = client.post(
        "/api/smart-config/run",
        json={
            "router_id": router["id"], "switch_ids": [switch["id"]],
            "departments": [{"name": "Sales", "users": 20}, {"name": "IT", "users": 10}],
            "routing_protocol": "ospf", "enable_dhcp": True, "deploy": False,
        },
        headers=h,
    ).json()
    gws = [d["gateway"] for d in res["plan"]["departments"]]
    assert len(gws) == 2

    # Sales gateway -> IT gateway: different VLANs, routed via the router
    r = client.post(
        "/api/monitoring/ping",
        json={"mode": "design", "source_ip": gws[0], "target": gws[1]},
        headers=h,
    )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True, r.text

    # an IP nobody owns -> never "successful"
    r2 = client.post(
        "/api/monitoring/ping",
        json={"mode": "design", "source_ip": gws[0], "target": "10.10.0.253"},
        headers=h,
    )
    assert r2.status_code == 200
    assert r2.json()["ok"] is False
    assert "No device" in r2.json()["reason"]


def test_auto_from_topology():
    h = _auth()
    devs = client.get("/api/devices", headers=h).json()
    r1 = next(d for d in devs if d["hostname"] == "R1")
    sw1 = next(d for d in devs if d["hostname"] == "SW1")
    pc1 = next(d for d in devs if d["hostname"] == "PC1")

    for a, b in [(pc1["id"], sw1["id"]), (sw1["id"], r1["id"])]:
        client.post(
            "/api/topology/connections",
            json={"a_device_id": a, "b_device_id": b, "link_type": "access"},
            headers=h,
        )
    # split: local networks only
    r = client.post("/api/smart-config/auto", json={"scope": "lan"}, headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert any(s["router"] == "R1" and s["lan"] for s in body["segments"])
    assert any(a["pc"] == "PC1" and a["ip"].startswith("192.168.") for a in body["dhcp"])
    r1cfg = next(x["config"] for x in body["results"] if x["device"] == "R1")
    assert "ip dhcp pool" in r1cfg and "router ospf 1" in r1cfg
    assert "vlan " not in r1cfg.lower()  # VLANs only belong on the switch

    # R1's LAN is 192.168.10.0/24 (seed mgmt IP) -> VLAN 100 (third octet x 10)
    vid = body["segments"][0]["lan"][0]["vlan_id"]
    assert vid == 100
    sw1cfg = next(x["config"] for x in body["results"] if x["device"] == "SW1")
    assert f"vlan {vid}" in sw1cfg and f"switchport access vlan {vid}" in sw1cfg

    # split: router-to-router only, must not wipe the LAN interface
    client.post("/api/devices", json={"name": "R2", "hostname": "R2", "device_type": "router"}, headers=h)
    r2 = next(d for d in client.get("/api/devices", headers=h).json()
              if d["device_type"] == "router" and d["hostname"] == "R2")
    client.post(
        "/api/topology/connections",
        json={"a_device_id": r1["id"], "b_device_id": r2["id"], "link_type": "access"},
        headers=h,
    )
    w = client.post("/api/smart-config/auto", json={"scope": "wan"}, headers=h)
    assert w.status_code == 200, w.text
    r1cfg2 = next(x["config"] for x in w.json()["results"] if x["device"] == "R1")
    assert "LAN " in r1cfg2 and "Link to" in r1cfg2  # both scopes present in the config
    # router-to-router link must be a /30
    link_line = next(ln for ln in r1cfg2.splitlines()
                     if ln.strip().startswith("ip address") and " 10." in ln)
    assert link_line.strip().endswith("255.255.255.252"), link_line


def test_router_to_router_link_is_slash30_even_with_typed_ip():
    h = _auth()
    devs = client.get("/api/devices", headers=h).json()
    r1 = next(d for d in devs if d["hostname"] == "R1")
    r2 = client.post(
        "/api/devices",
        json={"name": "RB", "hostname": "RB", "device_type": "router", "mgmt_ip": "10.0.1.2"},
        headers=h,
    ).json()
    client.post(
        "/api/topology/connections",
        json={"a_device_id": r1["id"], "b_device_id": r2["id"], "link_type": "access"},
        headers=h,
    )
    w = client.post("/api/smart-config/auto", json={"scope": "wan"}, headers=h)
    assert w.status_code == 200, w.text
    rbcfg = next(x["config"] for x in w.json()["results"] if x["device"] == "RB")
    assert "ip address 10.0.1.2 255.255.255.252" in rbcfg
    r1cfg = next(x["config"] for x in w.json()["results"] if x["device"] == "R1")
    assert "ip address 10.0.1.1 255.255.255.252" in r1cfg

    # BGP instead of OSPF
    b = client.post("/api/smart-config/auto", json={"routing": "bgp"}, headers=h)
    assert b.status_code == 200, b.text
    assert b.json()["routing"] == "bgp"
    bcfg = next(x["config"] for x in b.json()["results"] if x["device"] == "R1")
    assert "router bgp 650" in bcfg and "remote-as 650" in bcfg

    # NAT overload: R1 has both a LAN and a router link -> inside/outside
    nres = client.post("/api/smart-config/auto", json={"nat": True}, headers=h)
    assert nres.status_code == 200, nres.text
    assert nres.json()["nat"] is True
    ncfg = next(x["config"] for x in nres.json()["results"] if x["device"] == "R1")
    assert "ip nat inside" in ncfg and "ip nat outside" in ncfg
    assert "ip nat inside source list" in ncfg and "overload" in ncfg


def test_pc_gets_dhcp_address():
    h = _auth()
    devs = client.get("/api/devices", headers=h).json()
    router = next(d for d in devs if d["device_type"] == "router")
    switch = next(d for d in devs if d["device_type"] == "switch")
    pc = next(d for d in devs if d["device_type"] == "pc")

    client.post(
        "/api/smart-config/run",
        json={
            "router_id": router["id"], "switch_ids": [switch["id"]],
            "departments": [{"name": "Sales", "users": 30}],
            "routing_protocol": "ospf", "enable_dhcp": True, "deploy": False,
        },
        headers=h,
    )
    scopes = client.get("/api/devices/dhcp/scopes", headers=h).json()
    assert scopes and scopes[0]["free"] > 0
    subnet = scopes[0]["subnet"]

    r = client.post(f"/api/devices/{pc['id']}/dhcp", json={"subnet": subnet}, headers=h)
    assert r.status_code == 200, r.text
    ip = r.json()["mgmt_ip"]
    assert ip and ip.startswith("10.10.0.")

    # a second PC must get a different address
    pc2 = next(d for d in client.get("/api/devices", headers=h).json()
               if d["device_type"] == "pc" and d["id"] != pc["id"])
    r2 = client.post(f"/api/devices/{pc2['id']}/dhcp", json={"subnet": subnet}, headers=h)
    assert r2.json()["mgmt_ip"] != ip

    # release
    assert client.delete(f"/api/devices/{pc['id']}/dhcp", headers=h).json()["mgmt_ip"] is None


def test_dhcp_picks_the_chosen_network_of_several():
    """Two routers -> two LAN networks -> a PC can be handed an address from
    EITHER network (regression: VLAN-id collision used to force the first one)."""
    h = _auth()
    devs = client.get("/api/devices", headers=h).json()
    r1 = next(d for d in devs if d["hostname"] == "R1")
    sw1 = next(d for d in devs if d["hostname"] == "SW1")
    pc1 = next(d for d in devs if d["hostname"] == "PC1")
    r2 = client.post("/api/devices",
                     json={"name": "RB", "hostname": "RB", "device_type": "router"},
                     headers=h).json()
    swb = client.post("/api/devices",
                      json={"name": "SWB", "hostname": "SWB", "device_type": "switch"},
                      headers=h).json()
    for a, b in [(pc1["id"], sw1["id"]), (sw1["id"], r1["id"]), (swb["id"], r2["id"])]:
        client.post("/api/topology/connections",
                    json={"a_device_id": a, "b_device_id": b, "link_type": "access"}, headers=h)
    client.post("/api/smart-config/auto", json={"scope": "lan"}, headers=h)

    scopes = client.get("/api/devices/dhcp/scopes", headers=h).json()
    subnets = sorted(s["subnet"] for s in scopes)
    assert len(subnets) >= 2, scopes
    # PC1 is cabled to R1's LAN, but explicitly ask for the *other* network
    other = subnets[-1]
    r = client.post(f"/api/devices/{pc1['id']}/dhcp", json={"subnet": other}, headers=h)
    assert r.status_code == 200, r.text
    got = r.json()["mgmt_ip"]
    assert ipaddress.ip_address(got) in ipaddress.ip_network(other), (got, other)


@pytest.mark.parametrize("dtype,count_field,name", [
    ("ip_phone", "ip_phones", "PHONE1"),
    ("printer", "printers", "PRN1"),
])
def test_host_types_behave_like_a_pc(dtype, count_field, name):
    h = _auth()
    dev = client.post(
        "/api/devices",
        json={"name": name, "hostname": name, "device_type": dtype},
        headers=h,
    )
    assert dev.status_code == 201, dev.text
    did = dev.json()["id"]
    devs = client.get("/api/devices", headers=h).json()
    sw1 = next(d for d in devs if d["hostname"] == "SW1")
    r1 = next(d for d in devs if d["hostname"] == "R1")
    for a, b in [(did, sw1["id"]), (sw1["id"], r1["id"])]:
        client.post("/api/topology/connections",
                    json={"a_device_id": a, "b_device_id": b, "link_type": "access"}, headers=h)
    res = client.post("/api/smart-config/auto", json={"scope": "lan"}, headers=h)
    assert res.status_code == 200, res.text
    assert any(d["pc"] == name for d in res.json()["dhcp"])          # got a DHCP address
    assert client.get("/api/dashboard", headers=h).json()[count_field] >= 1


def test_server_roles_wire_into_the_routers():
    h = _auth()
    devs = client.get("/api/devices", headers=h).json()
    sw1 = next(d for d in devs if d["hostname"] == "SW1")
    r1 = next(d for d in devs if d["hostname"] == "R1")
    srv = client.post(
        "/api/devices",
        json={"name": "SRV1", "hostname": "SRV1", "device_type": "server",
              "services": "DNS,Syslog,NTP"},
        headers=h,
    )
    assert srv.status_code == 201, srv.text
    sid = srv.json()["id"]
    for a, b in [(sid, sw1["id"]), (sw1["id"], r1["id"])]:
        client.post("/api/topology/connections",
                    json={"a_device_id": a, "b_device_id": b, "link_type": "access"}, headers=h)
    res = client.post("/api/smart-config/auto", json={"scope": "lan"}, headers=h).json()

    # server keeps a static low address, reported as static
    srv_row = next(d for d in res["dhcp"] if d["pc"] == "SRV1")
    assert srv_row.get("static") is True
    srv_ip = srv_row["ip"]

    r1cfg = next(x["config"] for x in res["results"] if x["device"] == "R1")
    assert f"logging host {srv_ip}" in r1cfg
    assert f"ntp server {srv_ip}" in r1cfg
    assert f"dns-server {srv_ip}" in r1cfg          # handed to DHCP clients
    assert client.get("/api/dashboard", headers=h).json()["servers"] >= 1


def test_server_dhcp_role_makes_routers_relay():
    h = _auth()
    devs = client.get("/api/devices", headers=h).json()
    sw1 = next(d for d in devs if d["hostname"] == "SW1")
    r1 = next(d for d in devs if d["hostname"] == "R1")
    srv = client.post(
        "/api/devices",
        json={"name": "DHCPSRV", "hostname": "DHCPSRV", "device_type": "server",
              "services": "DHCP"},
        headers=h,
    ).json()
    for a, b in [(srv["id"], sw1["id"]), (sw1["id"], r1["id"])]:
        client.post("/api/topology/connections",
                    json={"a_device_id": a, "b_device_id": b, "link_type": "access"}, headers=h)
    res = client.post("/api/smart-config/auto", json={"scope": "lan"}, headers=h).json()
    srv_ip = next(d["ip"] for d in res["dhcp"] if d["pc"] == "DHCPSRV")
    r1cfg = next(x["config"] for x in res["results"] if x["device"] == "R1")
    assert f"ip helper-address {srv_ip}" in r1cfg
    assert "ip dhcp pool" not in r1cfg              # no local pool when relaying


def test_topology_graph_and_link():
    h = _auth()
    devices = client.get("/api/devices", headers=h).json()
    a, b = devices[0]["id"], devices[1]["id"]
    r = client.post(
        "/api/topology/connections",
        json={"a_device_id": a, "b_device_id": b, "a_interface": "Gi0/0", "b_interface": "Gi0/1", "link_type": "trunk"},
        headers=h,
    )
    assert r.status_code == 201
    graph = client.get("/api/topology", headers=h).json()
    assert len(graph["nodes"]) >= 2 and len(graph["edges"]) >= 1
