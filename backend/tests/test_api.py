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


def _device(h, name, device_type):
    """A fresh device of its own, so a manual config never pins the shared seed
    devices that later Smart Auto tests regenerate."""
    return client.post("/api/devices", json={"name": name, "hostname": name,
                                             "device_type": device_type}, headers=h).json()


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
    switch = _device(h, "SWMANUAL", "switch")
    payload = {
        "device_id": switch["id"],
        "hostname": "SWMANUAL",
        "vlans": [{"vlan_id": 30, "name": "HR"}],
        "interfaces": [{"name": "GigabitEthernet0/2", "mode": "access", "vlan_id": 30}],
        "dhcp": [],
        "deploy": False,
    }
    r = client.post("/api/manual-config/run", json=payload, headers=h)
    assert r.status_code == 200, r.text
    assert "switchport access vlan 30" in r.json()["config"]


def test_switch_gets_ssh_block_but_no_ip():
    h = _auth()
    sw = client.post(
        "/api/devices",
        json={
            "name": "SWSSH", "hostname": "SWSSH", "device_type": "switch",
            "mgmt_ip": "10.9.9.9", "ssh_username": "netadmin",
            "ssh_password": "cisco123", "ssh_secret": "en123",
        },
        headers=h,
    ).json()
    # switch never keeps an IP...
    assert sw["mgmt_ip"] is None
    # ...but the SSH credentials are kept
    assert sw["ssh_username"] == "netadmin"

    r = client.post(
        "/api/manual-config/run",
        json={
            "device_id": sw["id"],
            "vlans": [{"vlan_id": 20, "name": "DATA"}],
            "deploy": False,
        },
        headers=h,
    )
    assert r.status_code == 200, r.text
    cfg = r.json()["config"]
    assert "username netadmin privilege 15 secret cisco123" in cfg
    assert "transport input ssh" in cfg
    assert "login local" in cfg
    assert "ip address" not in cfg
    assert "interface vlan" not in cfg.lower()


def test_manual_config_ospf_and_bgp_on_router():
    h = _auth()
    router = _device(h, "RMANUAL1", "router")
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
    router = _device(h, "RMANUAL2", "router")
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
    scope = next(s for s in scopes if s["subnet"].startswith("10.10.0."))   # the Sales LAN
    assert scope["free"] > 0
    subnet = scope["subnet"]

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


def test_router_carries_several_hand_typed_lan_gateways():
    """Admin types 3 LAN gateways on a router; each new switch consumes the next
    one, the unused ones are kept for the next switch."""
    h = _auth()
    rc = client.post(
        "/api/devices",
        json={"name": "RLAN", "hostname": "RLAN", "device_type": "router"},
        headers=h,
    ).json()
    client.put(
        f"/api/devices/{rc['id']}",
        json={"extra_ips": [
            {"interface": "GigabitEthernet0/1", "address": "192.168.1.1/24"},
            {"interface": "GigabitEthernet0/2", "address": "192.168.5.1/24"},
            {"interface": "GigabitEthernet0/3", "address": "192.168.10.1/24"},
        ]},
        headers=h,
    )
    sw_a = client.post("/api/devices",
                       json={"name": "SWA1", "hostname": "SWA1", "device_type": "switch"},
                       headers=h).json()
    pc_a = client.post("/api/devices",
                       json={"name": "PCA1", "hostname": "PCA1", "device_type": "pc"},
                       headers=h).json()
    for a, b in [(pc_a["id"], sw_a["id"]), (sw_a["id"], rc["id"])]:
        client.post("/api/topology/connections",
                    json={"a_device_id": a, "b_device_id": b, "link_type": "access"}, headers=h)
    r = client.post("/api/smart-config/auto", json={"scope": "lan"}, headers=h).json()
    cfg1 = next(x["config"] for x in r["results"] if x["device"] == "RLAN")
    assert "ip address 192.168.1.1 255.255.255.0" in cfg1
    pca = next(d["ip"] for d in r["dhcp"] if d["pc"] == "PCA1")
    assert pca.startswith("192.168.1.")

    # add a second switch -> it must take 192.168.5.1, not a fresh pool subnet
    sw_b = client.post("/api/devices",
                       json={"name": "SWA2", "hostname": "SWA2", "device_type": "switch"},
                       headers=h).json()
    pc_b = client.post("/api/devices",
                       json={"name": "PCA2", "hostname": "PCA2", "device_type": "pc"},
                       headers=h).json()
    for a, b in [(pc_b["id"], sw_b["id"]), (sw_b["id"], rc["id"])]:
        client.post("/api/topology/connections",
                    json={"a_device_id": a, "b_device_id": b, "link_type": "access"}, headers=h)
    r2 = client.post("/api/smart-config/auto", json={"scope": "lan"}, headers=h).json()
    cfg2 = next(x["config"] for x in r2["results"] if x["device"] == "RLAN")
    assert "ip address 192.168.1.1 255.255.255.0" in cfg2
    assert "ip address 192.168.5.1 255.255.255.0" in cfg2
    pcb = next(d["ip"] for d in r2["dhcp"] if d["pc"] == "PCA2")
    assert pcb.startswith("192.168.5.")

    # the third hand-typed gateway is still waiting on the device
    rlan = next(d for d in client.get("/api/devices", headers=h).json()
                if d["hostname"] == "RLAN")
    ips = {a["ip"] for a in rlan["ip_addresses"]}
    assert "192.168.10.1/24" in ips


def test_new_switch_takes_a_hand_typed_gateway_added_later():
    """A router already has a switch on its first subnet. The admin adds a
    hand-typed gateway, cables a second switch -> the new switch takes the typed
    gateway (not a fresh pool subnet), and re-runs stay stable."""
    h = _auth()
    rz = client.post("/api/devices",
                     json={"name": "RZ", "hostname": "RZ", "device_type": "router"},
                     headers=h).json()
    sz1 = client.post("/api/devices", json={"name": "SZ1", "hostname": "SZ1", "device_type": "switch"}, headers=h).json()
    p1 = client.post("/api/devices", json={"name": "PZ1", "hostname": "PZ1", "device_type": "pc"}, headers=h).json()
    for a, b in [(p1["id"], sz1["id"]), (sz1["id"], rz["id"])]:
        client.post("/api/topology/connections",
                    json={"a_device_id": a, "b_device_id": b, "link_type": "access"}, headers=h)
    r1 = client.post("/api/smart-config/auto", json={"scope": "lan"}, headers=h).json()
    ip1 = next(d["ip"] for d in r1["dhcp"] if d["pc"] == "PZ1")

    client.put(
        f"/api/devices/{rz['id']}",
        # like the Edit form: every interface already listed, plus the new one
        json={"extra_ips": [
            {"interface": x["interface"], "address": x["ip"]}
            for x in client.get(f"/api/devices/{rz['id']}", headers=h).json()["ip_addresses"]
            if x["role"] != "mgmt"
        ] + [{"interface": "GigabitEthernet0/3", "address": "192.168.55.1/24"}]},
        headers=h,
    )
    sz2 = client.post("/api/devices", json={"name": "SZ2", "hostname": "SZ2", "device_type": "switch"}, headers=h).json()
    p2 = client.post("/api/devices", json={"name": "PZ2", "hostname": "PZ2", "device_type": "pc"}, headers=h).json()
    for a, b in [(p2["id"], sz2["id"]), (sz2["id"], rz["id"])]:
        client.post("/api/topology/connections",
                    json={"a_device_id": a, "b_device_id": b, "link_type": "access"}, headers=h)
    r2 = client.post("/api/smart-config/auto", json={"scope": "lan"}, headers=h).json()
    got2 = {d["pc"]: d["ip"] for d in r2["dhcp"]}
    assert got2["PZ1"] == ip1                              # first switch unchanged
    assert got2["PZ2"].startswith("192.168.55."), got2     # new switch takes the typed gw
    # stable
    r3 = client.post("/api/smart-config/auto", json={"scope": "lan"}, headers=h).json()
    got3 = {d["pc"]: d["ip"] for d in r3["dhcp"]}
    assert got3["PZ1"] == ip1 and got3["PZ2"] == got2["PZ2"]
    # a gateway typed under Devices -> Edit is still listed in the Smart summary
    seg = next(s for s in r3["segments"] if s["router"] == rz["hostname"])
    lan55 = next(l for l in seg["lan"] if l["gateway"] == "192.168.55.1")
    assert lan55["dhcp_range"] == "192.168.55.2 - 192.168.55.254" and lan55["hosts"] == 1


def test_pc_behind_second_switch_joins_that_switchs_subnet():
    """R1 -> sw_x (hand-typed 192.168.30.1) -> pc; sw_x is also cabled to another
    uplinked switch. The PC must land on 192.168.30.x, not the other subnet."""
    h = _auth()
    rx = client.post("/api/devices",
                     json={"name": "RX", "hostname": "RX", "device_type": "router",
                           "mgmt_ip": "192.168.20.1"},
                     headers=h).json()
    client.put(
        f"/api/devices/{rx['id']}",
        json={"extra_ips": [{"interface": "GigabitEthernet0/2", "address": "192.168.30.1/24"}]},
        headers=h,
    )
    sx = client.post("/api/devices", json={"name": "SX", "hostname": "SX", "device_type": "switch"}, headers=h).json()
    sy = client.post("/api/devices", json={"name": "SY", "hostname": "SY", "device_type": "switch"}, headers=h).json()
    pcx = client.post("/api/devices", json={"name": "PCX", "hostname": "PCX", "device_type": "pc"}, headers=h).json()
    pcy = client.post("/api/devices", json={"name": "PCY", "hostname": "PCY", "device_type": "pc"}, headers=h).json()
    for a, b in [
        (sx["id"], rx["id"]),        # SX uplinks to RX on the hand-typed 192.168.30.1
        (sy["id"], rx["id"]),        # SY uplinks to RX (mgmt 192.168.20.1)
        (sx["id"], sy["id"]),        # the L2 loop between the two segments
        (pcx["id"], sx["id"]),
        (pcy["id"], sy["id"]),
    ]:
        client.post("/api/topology/connections",
                    json={"a_device_id": a, "b_device_id": b, "link_type": "access"}, headers=h)
    res = client.post("/api/smart-config/auto", json={"scope": "lan"}, headers=h).json()
    got = {d["pc"]: d["ip"] for d in res["dhcp"]}
    assert got["PCX"].startswith("192.168.30."), got
    assert got["PCY"].startswith("192.168.20."), got
    rxcfg = next(x["config"] for x in res["results"] if x["device"] == "RX")
    assert "ip address 192.168.30.1 255.255.255.0" in rxcfg


def test_router_links_to_several_routers():
    """One router cabled to 3 routers: each link its own /30 on its own
    interface, and a hand-typed 10.x IP is honoured."""
    h = _auth()
    hub = client.post("/api/devices",
                      json={"name": "HUB", "hostname": "HUB", "device_type": "router"},
                      headers=h).json()
    client.put(
        f"/api/devices/{hub['id']}",
        json={"extra_ips": [{"interface": "GigabitEthernet0/5", "address": "10.7.7.1/30"}]},
        headers=h,
    )
    spokes = [
        client.post("/api/devices",
                    json={"name": f"SPK{i}", "hostname": f"SPK{i}", "device_type": "router"},
                    headers=h).json()
        for i in range(3)
    ]
    for s in spokes:
        client.post("/api/topology/connections",
                    json={"a_device_id": hub["id"], "b_device_id": s["id"], "link_type": "access"},
                    headers=h)
    r = client.post("/api/smart-config/auto", json={"scope": "wan"}, headers=h).json()
    hubcfg = next(x["config"] for x in r["results"] if x["device"] == "HUB")
    link_lines = [ln.strip() for ln in hubcfg.splitlines()
                  if ln.strip().startswith("ip address") and " 10." in ln]
    assert len(link_lines) == 3                         # three distinct links
    assert all(ln.endswith("255.255.255.252") for ln in link_lines)   # all /30
    assert "ip address 10.7.7.1 255.255.255.252" in hubcfg            # typed IP kept
    nets = {ln.split()[2] for ln in link_lines}
    assert len(nets) == 3                               # no address reused


def test_two_links_between_the_same_pair_of_routers():
    """R1 <-> R2 cabled twice (redundant / load-sharing links): both must get
    their own interface + /30, and re-running keeps both stable."""
    h = _auth()
    ra = client.post("/api/devices", json={"name": "RA", "hostname": "RA", "device_type": "router"}, headers=h).json()
    rb = client.post("/api/devices", json={"name": "RB2", "hostname": "RB2", "device_type": "router"}, headers=h).json()
    for _ in range(2):
        c = client.post("/api/topology/connections",
                        json={"a_device_id": ra["id"], "b_device_id": rb["id"], "link_type": "access"},
                        headers=h)
        assert c.status_code == 201, c.text

    r1 = client.post("/api/smart-config/auto", json={"scope": "wan"}, headers=h).json()
    racfg = next(x["config"] for x in r1["results"] if x["device"] == "RA")
    link_lines = [ln.strip() for ln in racfg.splitlines()
                  if ln.strip().startswith("ip address") and " 10." in ln]
    assert len(link_lines) == 2, racfg                 # both cables became real links
    ips = {ln.split()[2] for ln in link_lines}
    assert len(ips) == 2                               # on two distinct /30s

    graph = client.get("/api/topology", headers=h).json()
    ra_rb_edges = [e for e in graph["edges"]
                   if {e["source"], e["target"]} == {ra["id"], rb["id"]}]
    assert len(ra_rb_edges) == 2                       # neither cable got merged away

    # a second run must not collapse or move either link
    r2 = client.post("/api/smart-config/auto", json={"scope": "wan"}, headers=h).json()
    racfg2 = next(x["config"] for x in r2["results"] if x["device"] == "RA")
    assert racfg2 == racfg


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


def test_smart_auto_keeps_manual_config():
    h = _auth()
    r = client.post("/api/devices", json={"name": "RMAN", "hostname": "RMAN", "device_type": "router"}, headers=h).json()
    sw = client.post("/api/devices", json={"name": "SWMAN", "hostname": "SWMAN", "device_type": "switch"}, headers=h).json()
    pc = client.post("/api/devices", json={"name": "PCMAN", "hostname": "PCMAN", "device_type": "pc"}, headers=h).json()
    client.post("/api/topology/connections", json={"a_device_id": r["id"], "b_device_id": sw["id"]}, headers=h)
    client.post("/api/topology/connections", json={"a_device_id": sw["id"], "b_device_id": pc["id"]}, headers=h)

    manual = client.post("/api/manual-config/run", json={
        "device_id": r["id"], "hostname": "RMAN",
        "interfaces": [{"name": "GigabitEthernet0/0", "ip_address": "172.16.5.1",
                        "subnet_mask": "255.255.255.0", "description": "my LAN"}],
        "vlans": [], "dhcp": [], "deploy": False,
    }, headers=h).json()["config"]

    assert "172.16.5.1" in manual

    # Smart Auto still configures the router, but keeps the hand-typed interface + IP
    for _ in range(2):
        res = client.post("/api/smart-config/auto", json={"scope": "all"}, headers=h).json()
        cfg = next(x["config"] for x in res["results"] if x["device"] == "RMAN")
        assert "auto-generated" in cfg
        assert "interface GigabitEthernet0/0" in cfg
        assert "ip address 172.16.5.1 255.255.255.0" in cfg
        ips = [x["ip"] for x in client.get(f"/api/devices/{r['id']}", headers=h).json()["ip_addresses"]]
        assert "172.16.5.1/24" in ips
        # its only interface is manual, so RMAN is not in the Smart summary at all
        assert "RMAN" not in [s["router"] for s in res["segments"]]

    # it is also listed under Devices -> Edit -> Interface IP addresses ...
    listed = [x for x in client.get(f"/api/devices/{r['id']}", headers=h).json()["ip_addresses"]
              if x["role"] == "manual"]
    assert ("GigabitEthernet0/0", "172.16.5.1/24") in [(x["interface"], x["ip"]) for x in listed]
    # ... and saving that form unchanged keeps it a Manual Config interface
    client.put(f"/api/devices/{r['id']}", json={"extra_ips": [
        {"interface": x["interface"], "address": x["ip"]} for x in listed]}, headers=h)
    res = client.post("/api/smart-config/auto", json={"scope": "all"}, headers=h).json()
    assert "RMAN" not in [s["router"] for s in res["segments"]]
    cfg = next(x["config"] for x in res["results"] if x["device"] == "RMAN")
    assert "ip address 172.16.5.1 255.255.255.0" in cfg


def test_smart_auto_keeps_manual_router_link_ips():
    h = _auth()
    ra = _device(h, "RLINKA", "router")
    rb = _device(h, "RLINKB", "router")
    client.post("/api/topology/connections", json={"a_device_id": ra["id"], "b_device_id": rb["id"]}, headers=h)
    # first an auto run gives the link some /30 ...
    client.post("/api/smart-config/auto", json={"scope": "wan"}, headers=h)
    # ... then the admin types their own addresses on both ends
    for dev, ip in ((ra, "10.77.0.2"), (rb, "10.77.0.1")):
        client.post("/api/manual-config/run", json={
            "device_id": dev["id"],
            "interfaces": [{"name": "GigabitEthernet0/2", "ip_address": ip, "subnet_mask": "255.255.255.252"}],
            "deploy": False,
        }, headers=h)

    for _ in range(2):
        res = client.post("/api/smart-config/auto", json={"scope": "wan"}, headers=h).json()
        cfgs = {x["device"]: x["config"] for x in res["results"]}
        assert "ip address 10.77.0.2 255.255.255.252" in cfgs["RLINKA"]
        assert "ip address 10.77.0.1 255.255.255.252" in cfgs["RLINKB"]
        # the summary lists only what Smart Auto chose, never the hand-typed link
        seg_ips = [l["ip"] for s in res["segments"] for l in s["links"]]
        assert "10.77.0.2" not in seg_ips and "10.77.0.1" not in seg_ips

    # a new router cabled in is configured and listed as usual
    rc = _device(h, "RLINKC", "router")
    client.post("/api/topology/connections", json={"a_device_id": ra["id"], "b_device_id": rc["id"]}, headers=h)
    res = client.post("/api/smart-config/auto", json={"scope": "wan"}, headers=h).json()
    segs = {s["router"]: s for s in res["segments"]}
    assert [l["peer"] for l in segs["RLINKC"]["links"]] == ["RLINKA"]
    assert "RLINKC" in [l["peer"] for l in segs["RLINKA"]["links"]]
    assert "ip address 10.77.0.2 255.255.255.252" in next(
        x["config"] for x in res["results"] if x["device"] == "RLINKA")


def test_edit_form_lists_and_keeps_auto_interfaces():
    h = _auth()
    ra = _device(h, "REDITA", "router")
    rb = _device(h, "REDITB", "router")
    client.post("/api/topology/connections", json={"a_device_id": ra["id"], "b_device_id": rb["id"]}, headers=h)
    client.post("/api/smart-config/auto", json={"scope": "wan"}, headers=h)

    listed = [x for x in client.get(f"/api/devices/{ra['id']}", headers=h).json()["ip_addresses"]
              if x["role"] != "mgmt"]
    assert [x["role"] for x in listed] == ["link"]          # the auto link is in the form list
    form = [{"interface": x["interface"], "address": x["ip"]} for x in listed]

    # saving the form unchanged keeps it an automatic interface
    client.put(f"/api/devices/{ra['id']}", json={"extra_ips": form}, headers=h)
    after = client.get(f"/api/devices/{ra['id']}", headers=h).json()["ip_addresses"]
    assert [(x["interface"], x["ip"], x["role"]) for x in after if x["role"] != "mgmt"] == \
        [(x["interface"], x["ip"], "link") for x in listed]

    # adding another port from the form works too
    client.put(f"/api/devices/{ra['id']}", json={"extra_ips": form + [
        {"interface": "GigabitEthernet0/4", "address": "192.168.77.1/24"}]}, headers=h)
    after = {x["interface"]: x for x in client.get(f"/api/devices/{ra['id']}", headers=h).json()["ip_addresses"]}
    assert after["GigabitEthernet0/4"]["role"] == "manual"
    assert after[listed[0]["interface"]]["role"] == "link"

    # removing a row with the X deletes that interface
    client.put(f"/api/devices/{ra['id']}", json={"extra_ips": form}, headers=h)
    names = [x["interface"] for x in client.get(f"/api/devices/{ra['id']}", headers=h).json()["ip_addresses"]]
    assert "GigabitEthernet0/4" not in names


def test_overwrite_manual_lets_smart_auto_take_over():
    h = _auth()
    r = _device(h, "ROVER", "router")
    sw = _device(h, "SWOVER", "switch")
    client.post("/api/topology/connections", json={"a_device_id": r["id"], "b_device_id": sw["id"]}, headers=h)
    client.post("/api/manual-config/run", json={
        "device_id": r["id"],
        "interfaces": [{"name": "GigabitEthernet0/0", "ip_address": "172.20.0.1", "subnet_mask": "255.255.255.0"}],
        "deploy": False,
    }, headers=h)

    # unticked (default): the hand-typed IP stays
    res = client.post("/api/smart-config/auto", json={"scope": "lan"}, headers=h).json()
    assert "ip address 172.20.0.1 255.255.255.0" in next(x["config"] for x in res["results"] if x["device"] == "ROVER")

    # ticked: Smart Auto replaces it with its own address - nothing mixed
    res = client.post("/api/smart-config/auto", json={"scope": "lan", "overwrite_manual": True}, headers=h).json()
    cfg = next(x["config"] for x in res["results"] if x["device"] == "ROVER")
    assert "172.20.0.1" not in cfg
    seg = next(s for s in res["segments"] if s["router"] == "ROVER")
    assert seg["lan"] and seg["lan"][0]["gateway"].startswith("192.168.")
    roles = {x["role"] for x in client.get(f"/api/devices/{r['id']}", headers=h).json()["ip_addresses"]}
    assert "manual" not in roles


def test_router_and_switch_cables_are_always_access():
    h = _auth()
    r1, r2 = _device(h, "RCAB1", "router"), _device(h, "RCAB2", "router")
    s1, s2 = _device(h, "SCAB1", "switch"), _device(h, "SCAB2", "switch")
    pc = _device(h, "PCCAB", "pc")
    for a, b in [(r1, r2), (s1, s2), (r1, s1)]:
        c = client.post("/api/topology/connections", json={
            "a_device_id": a["id"], "b_device_id": b["id"], "link_type": "trunk"}, headers=h).json()
        assert c["link_type"] == "access"
    # a cable to an endpoint keeps whatever was chosen
    c = client.post("/api/topology/connections", json={
        "a_device_id": s2["id"], "b_device_id": pc["id"], "link_type": "trunk"}, headers=h).json()
    assert c["link_type"] == "trunk"


def test_to_peer_only_on_double_cabled_links():
    h = _auth()
    ra, rb, rc = (_device(h, n, "router") for n in ("RPAR1", "RPAR2", "RPAR3"))
    for a, b in [(ra, rb), (ra, rb), (ra, rc)]:            # two cables A-B, one cable A-C
        client.post("/api/topology/connections", json={"a_device_id": a["id"], "b_device_id": b["id"]}, headers=h)
    client.post("/api/smart-config/auto", json={"scope": "wan"}, headers=h)

    rows = [x for x in client.get(f"/api/devices/{ra['id']}", headers=h).json()["ip_addresses"]
            if x["role"] == "link"]
    assert len(rows) == 3
    assert sorted(x["parallel"] for x in rows) == [False, True, True]


def test_ping_path_lists_only_routers_crossed():
    h = _auth()
    ra, rb, rc = (_device(h, n, "router") for n in ("RPATH1", "RPATH2", "RPATH3"))
    sa, sc = _device(h, "SPATH1", "switch"), _device(h, "SPATH3", "switch")
    pa1, pa2, pc = _device(h, "PPATH1", "pc"), _device(h, "PPATH2", "pc"), _device(h, "PPATH3", "pc")
    for a, b in [(ra, rb), (rb, rc), (ra, sa), (sa, pa1), (sa, pa2), (rc, sc), (sc, pc)]:
        client.post("/api/topology/connections", json={"a_device_id": a["id"], "b_device_id": b["id"]}, headers=h)
    res = client.post("/api/smart-config/auto", json={"scope": "all"}, headers=h).json()
    ip = {d["pc"]: d["ip"] for d in res["dhcp"]}

    same = client.post("/api/monitoring/ping", json={"mode": "design", "source_ip": ip["PPATH1"],
                                                     "target": ip["PPATH2"]}, headers=h).json()
    assert same["ok"] and same.get("via") == []                     # same LAN, no router
    far = client.post("/api/monitoring/ping", json={"mode": "design", "source_ip": ip["PPATH1"],
                                                    "target": ip["PPATH3"]}, headers=h).json()
    assert far["ok"] and far["via"] == ["RPATH1", "RPATH2", "RPATH3"]


def test_packet_follows_the_cables():
    h = _auth()
    ra, rb, rx = (_device(h, n, "router") for n in ("RPKT1", "RPKT2", "RPKT3"))
    sa, sb = _device(h, "SPKT1", "switch"), _device(h, "SPKT2", "switch")
    pa, pa2, pb, lone = (_device(h, n, "pc") for n in ("PPKT1", "PPKT2", "PPKT3", "PPKT4"))
    cable = {}
    for a, b in [(pa, sa), (pa2, sa), (sa, ra), (ra, rb), (rb, sb), (sb, pb), (ra, rx)]:
        cable[a["name"], b["name"]] = client.post("/api/topology/connections", json={
            "a_device_id": a["id"], "b_device_id": b["id"]}, headers=h).json()["id"]
    client.post("/api/smart-config/auto", json={"scope": "all"}, headers=h)

    def send(a, b):
        r = client.post("/api/monitoring/packet", headers=h, json={
            "source_device_id": a["id"], "target_device_id": b["id"]})
        assert r.status_code == 200, r.text
        return r.json()

    # PC -> PC across two routers: every device in order, and the real cables
    far = send(pa, pb)
    assert far["ok"] and far["path"] == ["PPKT1", "SPKT1", "RPKT1", "RPKT2", "SPKT2", "PPKT3"]
    assert [x["connection_id"] for x in far["hops"]] == [
        cable["PPKT1", "SPKT1"], cable["SPKT1", "RPKT1"], cable["RPKT1", "RPKT2"],
        cable["RPKT2", "SPKT2"], cable["SPKT2", "PPKT3"]]
    # PC -> its own router, PC -> PC in one LAN, router -> PC, router -> router
    assert send(pa, ra)["path"] == ["PPKT1", "SPKT1", "RPKT1"]
    assert send(pa, pa2)["path"] == ["PPKT1", "SPKT1", "PPKT2"]
    assert send(ra, pb)["path"] == ["RPKT1", "RPKT2", "SPKT2", "PPKT3"]
    assert send(rx, rb)["path"] == ["RPKT3", "RPKT1", "RPKT2"]

    # failures: no IP on the target (dropped at the first router), an uncabled
    # host in the same subnet, and a switch
    no_ip = send(pa, lone)
    assert not no_ip["ok"] and no_ip["path"] == ["PPKT1", "SPKT1", "RPKT1"]
    ip = client.get(f"/api/devices/{pa['id']}", headers=h).json()["mgmt_ip"]
    client.put(f"/api/devices/{lone['id']}", json={"mgmt_ip": ip.rsplit(".", 1)[0] + ".200"}, headers=h)
    uncabled = send(pa, lone)
    assert not uncabled["ok"] and uncabled["hops"] == []
    assert not send(pa, sb)["ok"]
    assert client.post("/api/monitoring/packet", headers=h, json={
        "source_device_id": pa["id"], "target_device_id": pa["id"]}).status_code == 400


def test_device_info_for_the_hover_box():
    h = _auth()
    r, r2 = _device(h, "RTIP1", "router"), _device(h, "RTIP2", "router")
    sw, pc, idle = _device(h, "STIP1", "switch"), _device(h, "PTIP1", "pc"), _device(h, "PTIP2", "pc")
    for a, ai, b, bi in [(r, "Gi0/1", sw, "FastEthernet0/1"), (sw, "FastEthernet0/2", pc, "eth0"),
                         (r, "GigabitEthernet0/5", r2, "GigabitEthernet0/5")]:
        client.post("/api/topology/connections", headers=h, json={
            "a_device_id": a["id"], "b_device_id": b["id"], "a_interface": ai, "b_interface": bi})
    res = client.post("/api/smart-config/auto", json={"scope": "all"}, headers=h).json()
    vlan = next(x["vlan_id"] for x in res["results"] if x["device"] == "STIP1")
    ip = next(x["ip"] for x in res["dhcp"] if x["pc"] == "PTIP1")

    def info(d):
        data = client.get(f"/api/topology/devices/{d['id']}/info", headers=h).json()
        return data, {p["port"]: p for p in data["ports"]}

    data, ports = info(r)
    assert (data["name"], data["hostname"], data["type"]) == ("RTIP1", "RTIP1", "router")
    lan = next(p for p in ports.values() if p["vlan"])
    assert lan["link"] == "Up" and lan["vlan"] == vlan and lan["ip"].endswith("/24")
    assert any(p["ip"].startswith("10.") and p["ip"].endswith("/30") and p["vlan"] is None
               for p in ports.values())
    data, ports = info(sw)
    assert data["spare_vlan"] == vlan
    assert {n: (p["link"], p["vlan"], p["ip"]) for n, p in ports.items()} == {
        "FastEthernet0/1": ("Up", vlan, None), "FastEthernet0/2": ("Up", vlan, None)}
    _, ports = info(pc)
    assert ports["eth0"] == {"port": "eth0", "link": "Up", "vlan": vlan, "ip": f"{ip}/24"}
    _, ports = info(idle)
    assert ports["eth0"] == {"port": "eth0", "link": "Down", "vlan": None, "ip": None}
    assert client.get("/api/topology/devices/999999/info", headers=h).status_code == 404


def test_vlan_ids_for_three_digit_networks():
    h = _auth()
    r = _device(h, "RVLAN1", "router")
    client.put(f"/api/devices/{r['id']}", headers=h, json={"extra_ips": [
        {"interface": "GigabitEthernet0/1", "address": "192.168.150.1/24"},
        {"interface": "GigabitEthernet0/2", "address": "192.168.100.1/24"}]})
    for n in ("SVLAN1", "SVLAN2"):
        client.post("/api/topology/connections", headers=h, json={
            "a_device_id": r["id"], "b_device_id": _device(h, n, "switch")["id"]})

    def vlans():
        return {v["subnet"]: v["vlan_id"]
                for v in client.get(f"/api/devices/{r['id']}/vlans", headers=h).json()}

    res = client.post("/api/smart-config/auto", json={"scope": "lan"}, headers=h).json()
    got = vlans()
    assert got["192.168.150.0/24"] == 150
    # 100 already belongs to another LAN in this database -> the x10 number is used
    assert got["192.168.100.0/24"] == 1000
    by_net = {l["network"]: l["vlan_id"] for s in res["segments"] for l in s["lan"]}
    assert 100 in by_net.values() and len(set(by_net.values())) == len(by_net)
    # a run for the router links only keeps the very same numbers
    client.post("/api/smart-config/auto", json={"scope": "wan"}, headers=h)
    assert vlans() == got
    # nothing is blocked: the admin may still type any VLAN by hand
    sw = _device(h, "SVLAN3", "switch")
    for vid in (100, 1000, 2000):
        m = client.post("/api/manual-config/run", headers=h, json={
            "device_id": sw["id"], "vlans": [{"vlan_id": vid, "name": f"V{vid}"}], "deploy": False})
        assert m.status_code == 200 and f"vlan {vid}" in m.json()["config"]


def test_api_docs_can_call_the_api_from_a_browser():
    h = {**_auth(), "Sec-Fetch-Site": "same-origin"}
    base = "http://localhost:8000"
    for page in ("/docs", "/redoc"):
        assert client.get("/api/devices", headers={**h, "Referer": base + page}).status_code == 200
    # an old cached UI is still sent back to the login page
    old = client.get("/api/devices", headers={**h, "Referer": base + "/devices"})
    assert old.status_code == 401 and old.headers["clear-site-data"] == '"cache"'
    assert client.get("/api/devices", headers={**h, "X-UI-Build": "1"}).status_code == 200


def test_network_and_broadcast_addresses_are_refused():
    h = _auth()
    r = _device(h, "RBADIP", "router")
    url = f"/api/devices/{r['id']}"

    def save(addr):
        return client.put(url, headers=h, json={"extra_ips": [{"interface": "GigabitEthernet0/1", "address": addr}]})

    for bad in ("10.91.1.0/30", "10.91.1.3/30", "192.168.91.0", "192.168.91.255/24"):
        res = save(bad)
        assert res.status_code == 400 and "cannot use it" in res.json()["detail"], bad
    assert save("not-an-ip").status_code == 400
    assert client.get(url, headers=h).json()["ip_addresses"] == []
    for good in ("10.91.1.1/30", "10.91.1.0/31", "192.168.91.254/24"):
        assert save(good).status_code == 200, good

    def manual(ip, mask):
        return client.post("/api/manual-config/run", headers=h, json={"device_id": r["id"], "deploy": False, "interfaces": [
            {"name": "GigabitEthernet0/2", "ip_address": ip, "subnet_mask": mask}]})

    assert manual("10.92.1.0", "255.255.255.252").status_code == 400
    assert manual("10.92.1.2", "255.255.255.252").status_code == 200


def test_smart_auto_repairs_an_unusable_link_address():
    from database import SessionLocal
    from models import Interface
    h = _auth()
    ra, rb = _device(h, "RFIX1", "router"), _device(h, "RFIX2", "router")
    client.post("/api/topology/connections", headers=h, json={
        "a_device_id": ra["id"], "b_device_id": rb["id"],
        "a_interface": "GigabitEthernet0/5", "b_interface": "GigabitEthernet0/5"})
    db = SessionLocal()      # what an older version could leave behind
    for dev, ip in ((ra, "10.93.1.0"), (rb, "10.93.1.1")):
        db.add(Interface(device_id=dev["id"], name="GigabitEthernet0/5", ip_address=ip, mode="routed",
                         subnet_mask="255.255.255.252", description="link to peer", enabled=True))
    db.commit(); db.close()
    ping = client.post("/api/monitoring/ping", headers=h, json={
        "mode": "design", "source_ip": "10.93.1.1", "target": "10.93.1.0"}).json()
    assert not ping["ok"] and "network address" in ping["reason"]
    for _ in range(2):
        cfg = {x["device"]: x["config"] for x in client.post(
            "/api/smart-config/auto", json={"scope": "wan"}, headers=h).json()["results"]}
        assert "ip address 10.93.1.2 255.255.255.252" in cfg["RFIX1"]
        assert "ip address 10.93.1.1 255.255.255.252" in cfg["RFIX2"]      # the good end is kept
    assert client.post("/api/monitoring/ping", headers=h, json={
        "mode": "design", "source_ip": "10.93.1.1", "target": "10.93.1.2"}).json()["ok"]


def test_every_cabled_switch_port_is_in_the_vlan():
    h = _auth()
    r, sw, pr = _device(h, "RGIG", "router"), _device(h, "SGIG", "switch"), _device(h, "PGIG", "printer")
    for a, ai, b, bi in [(sw, "FastEthernet0/1", r, "GigabitEthernet0/1"), (sw, "GigabitEthernet0/1", pr, "eth0")]:
        client.post("/api/topology/connections", headers=h, json={
            "a_device_id": a["id"], "b_device_id": b["id"], "a_interface": ai, "b_interface": bi})
    res = client.post("/api/smart-config/auto", json={"scope": "lan"}, headers=h).json()
    row = next(x for x in res["results"] if x["device"] == "SGIG")
    block = row["config"].split("interface GigabitEthernet0/1\n")[1].split("!")[0]
    assert f"switchport access vlan {row['vlan_id']}" in block and "portfast" in block
    ports = client.get(f"/api/topology/devices/{pr['id']}/info", headers=h).json()["ports"]
    assert ports[0]["vlan"] == row["vlan_id"]

    # a router uplink on a Gigabit port is written once, as the uplink
    r2, s2 = _device(h, "RGIG2", "router"), _device(h, "SGIG2", "switch")
    client.post("/api/topology/connections", headers=h, json={
        "a_device_id": s2["id"], "b_device_id": r2["id"],
        "a_interface": "GigabitEthernet0/1", "b_interface": "GigabitEthernet0/1"})
    res = client.post("/api/smart-config/auto", json={"scope": "lan"}, headers=h).json()
    cfg = next(x["config"] for x in res["results"] if x["device"] == "SGIG2")
    assert cfg.count("interface GigabitEthernet0/1\n") == 1 and "Uplink to RGIG2" in cfg
