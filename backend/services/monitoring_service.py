"""Monitoring module (MVP): reachability + ping.

Two kinds of check:
  * ping_from_server  -> ICMP from the host running the backend to a device
  * ping_from_device  -> SSH into a device and run Cisco `ping <target>`, parse
                          the "Success rate is X percent (m/n)" line.

Note: `ping_from_device` needs the source device to have SSH reachable from this
host (works with GNS3/EVE-NG bridged to your LAN; Cisco Packet Tracer devices are
not reachable from the host and must be tested inside Packet Tracer).
"""
from __future__ import annotations

import ipaddress
import platform
import re
import subprocess

from sqlalchemy.orm import Session

from config import settings
from models import Connection, Device, Interface, Vlan

_SUCCESS_RE = re.compile(r"Success rate is (\d+) percent \((\d+)/(\d+)\)")


# --------------------------------------------------------------------------- #
# Simulated reachability - works fully offline (ideal for Cisco Packet Tracer,
# where the platform cannot reach the devices). It answers: "according to the
# configuration stored on the platform, SHOULD these two IPs be able to ping?"
# --------------------------------------------------------------------------- #
def _net_of(ip: str, mask: str) -> ipaddress.IPv4Network | None:
    try:
        return ipaddress.ip_network(f"{ip}/{mask}", strict=False)
    except ValueError:
        return None


ASSUMED_HOST_PREFIX = 24  # for a device IP given without a mask


def _device_types(db: Session) -> dict[int, str]:
    return {d.id: d.device_type for d in db.query(Device).all()}


def _real_networks(db: Session) -> list[dict]:
    """Genuine L3 segments. Switches are pure Layer 2 and contribute nothing."""
    segs: list[dict] = []
    dtype = _device_types(db)
    for iface in db.query(Interface).all():
        if iface.ip_address and iface.subnet_mask and dtype.get(iface.device_id) != "switch":
            n = _net_of(iface.ip_address, iface.subnet_mask)
            if n:
                segs.append({"net": n, "device_id": iface.device_id,
                             "is_router": dtype.get(iface.device_id) == "router"})
    for v in db.query(Vlan).all():
        if v.subnet and dtype.get(v.device_id) != "switch":
            try:
                n = ipaddress.ip_network(v.subnet, strict=False)
            except ValueError:
                continue
            segs.append({"net": n, "device_id": v.device_id,
                         "is_router": dtype.get(v.device_id) == "router"})
    return segs


def _assigned_ips(db: Session) -> dict[str, dict]:
    """Every IP actually configured on a device. Switches never carry an IP."""
    dtype = _device_types(db)
    out: dict[str, dict] = {}
    for d in db.query(Device).all():
        if d.mgmt_ip and d.device_type != "switch":
            out[d.mgmt_ip] = {"device_id": d.id, "label": f"{d.hostname} ({d.device_type})",
                              "is_router": d.device_type == "router"}
    for iface in db.query(Interface).all():
        if iface.ip_address and dtype.get(iface.device_id) != "switch":
            out[iface.ip_address] = {"device_id": iface.device_id, "label": iface.name,
                                     "is_router": dtype.get(iface.device_id) == "router"}
    for v in db.query(Vlan).all():
        if v.gateway and dtype.get(v.device_id) != "switch":
            out.setdefault(v.gateway, {"device_id": v.device_id, "label": f"VLAN {v.vlan_id} gateway",
                                       "is_router": dtype.get(v.device_id) == "router"})
    return out


def _mgmt_networks(db: Session) -> list[dict]:
    """Each device IP as an /24 segment - only to link two *assigned* IPs that
    sit in the same /24 (e.g. router 192.168.10.2 <-> PC 192.168.10.4).
    Switches excluded (Layer 2, no IP)."""
    segs = []
    for d in db.query(Device).all():
        if d.mgmt_ip and d.device_type != "switch":
            n = _net_of(d.mgmt_ip, str(ASSUMED_HOST_PREFIX))
            if n:
                segs.append({"net": n, "device_id": d.id, "is_router": d.device_type == "router"})
    return segs


class _UF:
    def __init__(self):
        self.p: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a: str, b: str) -> None:
        self.p[self.find(a)] = self.find(b)


def simulate_reachability(db: Session, source: str, target: str) -> dict:
    real = _real_networks(db)
    assigned = _assigned_ips(db)
    mgmt = _mgmt_networks(db)
    hostnames = {d.id: d.hostname for d in db.query(Device).all()}

    if not real and not assigned:
        return {"ok": False, "reason": "No IP configuration yet. Run Smart Auto Config first."}

    def resolve(ip: str):
        """-> (network, is_router_ip) only for an IP that is actually assigned to
        a device. None otherwise (so unassigned IPs never report success)."""
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return None
        if str(addr) not in assigned:
            return None
        info = assigned[str(addr)]
        in_real = [s["net"] for s in real if addr in s["net"]]
        if in_real:
            net = max(in_real, key=lambda n: n.prefixlen)
        else:
            m = [s["net"] for s in mgmt if addr in s["net"]]
            net = max(m, key=lambda n: n.prefixlen) if m else ipaddress.ip_network(f"{addr}/32")
        return net, info["is_router"]

    r_src, r_dst = resolve(source), resolve(target)
    if r_src is None:
        return {"ok": False,
                "reason": f"No device has the IP {source}. Assign it to a device first "
                          f"(Devices -> Edit -> IP address)."}
    if r_dst is None:
        return {"ok": False,
                "reason": f"No device has the IP {target}. Assign it to a device first "
                          f"(Devices -> Edit -> IP address)."}

    src_net, src_is_router = r_src
    dst_net, _ = r_dst

    if src_net == dst_net:
        return {"ok": True, "via": [],
                "reason": f"Same subnet {src_net} - Layer 2, no routing needed.",
                "source_net": str(src_net), "target_net": str(dst_net)}

    # ---- reachability graph -------------------------------------------------
    # 1) a router forwards between all of its own networks
    # 2) devices wired together in the topology (directly, or a PC/switch chain
    #    up to a router) can exchange traffic - the routers along the way run
    #    OSPF, so their networks become mutually reachable
    uf = _UF()
    router_ids = {d.id for d in db.query(Device).filter(Device.device_type == "router").all()}

    dev_nets: dict[int, list[str]] = {}
    for s in real + mgmt:
        dev_nets.setdefault(s["device_id"], []).append(str(s["net"]))
    for did, subs in dev_nets.items():
        for s in subs[1:]:
            uf.union(subs[0], s)

    by_router = {rid: subs for rid, subs in dev_nets.items() if rid in router_ids}

    adj: dict[int, set[int]] = {}
    for c in db.query(Connection).all():
        adj.setdefault(c.a_device_id, set()).add(c.b_device_id)
        adj.setdefault(c.b_device_id, set()).add(c.a_device_id)

    def routers_reachable_from(start: int) -> set[int]:
        seen, stack, found = {start}, [start], set()
        while stack:
            for nb in adj.get(stack.pop(), ()):
                if nb in seen:
                    continue
                seen.add(nb)
                if nb in router_ids:
                    found.add(nb)          # stop here - don't cross a router
                else:
                    stack.append(nb)
        return found

    for d in db.query(Device).all():
        reached = routers_reachable_from(d.id)
        if d.id in router_ids:
            reached.add(d.id)
        roots = [by_router[r][0] for r in reached if r in by_router]
        anchors = dev_nets.get(d.id, []) + roots
        for a in anchors[1:]:
            uf.union(anchors[0], a)

    def component_routers(net: str) -> list[str]:
        return sorted({
            hostnames[rid] for rid, subs in by_router.items()
            if uf.find(subs[0]) == uf.find(net)
        })

    src_component_routers = component_routers(str(src_net))
    src_has_gateway = src_is_router or bool(src_component_routers)
    if not src_has_gateway:
        return {"ok": False, "source_net": str(src_net), "target_net": str(dst_net),
                "reason": f"Subnet {src_net} has no gateway and is not cabled to a router - "
                          f"hosts there cannot leave the subnet."}

    if uf.find(str(src_net)) == uf.find(str(dst_net)):
        via = component_routers(str(src_net))
        return {"ok": True, "via": via,
                "reason": (f"Routed path via {', '.join(via)}."
                           if via else "Connected path."),
                "source_net": str(src_net), "target_net": str(dst_net)}

    return {"ok": False, "source_net": str(src_net), "target_net": str(dst_net),
            "reason": f"No path between {src_net} and {dst_net} - the devices are not "
                      f"cabled together (or a router-to-router link is missing)."}


def ping_from_server(host: str, count: int = 4) -> dict:
    if not host:
        return {"ok": False, "output": "no IP set", "loss_pct": 100}
    flag = "-n" if platform.system() == "Windows" else "-c"
    try:
        proc = subprocess.run(
            ["ping", flag, str(count), host], capture_output=True, text=True, timeout=15
        )
        out = proc.stdout + proc.stderr
        ok = proc.returncode == 0
        m = re.search(r"\((\d+)% (?:loss|packet loss)\)", out)
        loss = int(m.group(1)) if m else (0 if ok else 100)
        return {"ok": ok, "output": out.strip(), "loss_pct": loss}
    except subprocess.TimeoutExpired:
        return {"ok": False, "output": "ping timed out", "loss_pct": 100}
    except OSError as exc:
        return {"ok": False, "output": str(exc), "loss_pct": 100}


def ping_from_device(device, target: str, count: int = 5) -> dict:
    """SSH into `device` and run `ping <target>`."""
    from netmiko import ConnectHandler

    if not device.mgmt_ip:
        return {"ok": False, "output": f"{device.hostname}: no management IP set", "loss_pct": 100}

    params = {
        "device_type": device.netmiko_driver or "cisco_ios",
        "host": device.mgmt_ip,
        "username": device.ssh_username or "",
        "password": device.ssh_password or "",
        "secret": device.ssh_secret or device.ssh_password or "",
        "timeout": settings.ssh_timeout,
        "fast_cli": False,
    }
    try:
        conn = ConnectHandler(**params)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "output": f"SSH to {device.hostname} failed: {exc}", "loss_pct": 100}

    try:
        if device.ssh_secret:
            conn.enable()
        output = conn.send_command(f"ping {target} repeat {count}", read_timeout=30)
    finally:
        conn.disconnect()

    m = _SUCCESS_RE.search(output)
    if m:
        pct, rx, tx = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return {
            "ok": pct > 0,
            "output": output.strip(),
            "loss_pct": 100 - pct,
            "received": rx,
            "sent": tx,
        }
    return {"ok": "!!!" in output, "output": output.strip(), "loss_pct": 0 if "!!!" in output else 100}
