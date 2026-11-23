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
        """-> (network, is_router_ip, device_id) only for an IP that is actually assigned to
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
        return net, info["is_router"], info["device_id"]

    r_src, r_dst = resolve(source), resolve(target)
    if r_src is None:
        return {"ok": False,
                "reason": f"No device has the IP {source}. Assign it to a device first "
                          f"(Devices -> Edit -> IP address)."}
    if r_dst is None:
        return {"ok": False,
                "reason": f"No device has the IP {target}. Assign it to a device first "
                          f"(Devices -> Edit -> IP address)."}

    for ip, (net, _, _) in ((source, r_src), (target, r_dst)):
        if net.prefixlen < 31 and ipaddress.ip_address(ip) in (net.network_address, net.broadcast_address):
            kind = "network" if ipaddress.ip_address(ip) == net.network_address else "broadcast"
            return {"ok": False, "reason": f"{ip} is the {kind} address of {net} - no device can use it.",
                    "source_net": str(r_src[0]), "target_net": str(r_dst[0])}

    src_net, src_is_router, src_dev = r_src
    dst_net, _, dst_dev = r_dst

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

    def gateways(dev: int, net) -> set[int]:
        """The router(s) a host's traffic enters/leaves the routed network on."""
        if dev in router_ids:
            return {dev}
        own = {x["device_id"] for x in real if x["is_router"] and x["net"] == net}
        return own or routers_reachable_from(dev)

    def _router_path(src_dev: int, src_net, dst_dev: int, dst_net) -> list[int]:
        """Shortest chain of routers from the source's gateway to the
        destination's gateway - only the routers the packet really crosses."""
        starts, goals = gateways(src_dev, src_net), gateways(dst_dev, dst_net)
        prev: dict[int, int | None] = {r: None for r in starts}
        queue = sorted(starts)
        while queue:
            cur = queue.pop(0)
            if cur in goals:
                path = []
                while cur is not None:
                    path.append(cur)
                    cur = prev[cur]
                return path[::-1]
            for nb in sorted(routers_reachable_from(cur)):
                if nb not in prev:
                    prev[nb] = cur
                    queue.append(nb)
        return []

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
        via_ids = _router_path(src_dev, src_net, dst_dev, dst_net)
        via = [hostnames[r] for r in via_ids] or component_routers(str(src_net))
        if len(via) == 1:
            reason = f"Routed by {via[0]} - both networks are on it."
        elif via:
            reason = f"Leaves through {via[0]}, enters through {via[-1]}: {' -> '.join(via)}."
        else:
            reason = "Connected path."
        return {"ok": True, "via": via, "via_ids": via_ids, "reason": reason,
                "source_net": str(src_net), "target_net": str(dst_net)}

    return {"ok": False, "source_net": str(src_net), "target_net": str(dst_net),
            "reason": f"No path between {src_net} and {dst_net} - the devices are not "
                      f"cabled together (or a router-to-router link is missing)."}


def _packet_ip(db: Session, d: Device) -> str | None:
    if d.device_type == "router":
        ips = [i for i in db.query(Interface)
               .filter(Interface.device_id == d.id, Interface.ip_address.isnot(None))
               .order_by(Interface.id)]
        for i in ips:
            net = _net_of(i.ip_address, i.subnet_mask)
            if net and (net.prefixlen >= 31 or ipaddress.ip_address(i.ip_address)
                        not in (net.network_address, net.broadcast_address)):
                return i.ip_address
        if ips:
            return ips[0].ip_address
    return d.mgmt_ip


def trace_packet(db: Session, src_id: int, dst_id: int) -> dict:
    """Send one envelope from a device to another: the same verdict as the ping
    test, plus every cable it crosses on the way (`hops`). When it cannot arrive,
    `hops` is how far it gets before it is dropped."""
    devices = {d.id: d for d in db.query(Device).all()}
    src, dst = devices.get(src_id), devices.get(dst_id)
    if src is None or dst is None:
        raise ValueError("Device not found.")
    if src_id == dst_id:
        raise ValueError("Choose two different devices.")

    adj: dict[int, list[tuple[int, int]]] = {}
    for c in db.query(Connection).order_by(Connection.id).all():
        adj.setdefault(c.a_device_id, []).append((c.id, c.b_device_id))
        adj.setdefault(c.b_device_id, []).append((c.id, c.a_device_id))

    def layer2(start: int, is_goal) -> list[dict] | None:
        """Cables from `start` to the nearest goal, through switches (and the
        pass-through port of an IP phone) only - never through a PC or a router."""
        prev: dict[int, tuple[int, int] | None] = {start: None}
        queue = [start]
        while queue:
            cur = queue.pop(0)
            if cur != start and is_goal(cur):
                hops = []
                while prev[cur] is not None:
                    conn_id, before = prev[cur]
                    hops.append({"connection_id": conn_id, "from": before, "to": cur})
                    cur = before
                return hops[::-1]
            if cur != start and devices[cur].device_type not in ("switch", "ip_phone"):
                continue
            for conn_id, nb in adj.get(cur, []):
                if nb in devices and nb not in prev:
                    prev[nb] = (conn_id, cur)
                    queue.append(nb)
        return None

    def result(ok: bool, reason: str, hops: list[dict]) -> dict:
        path = [src.name] + [devices[h["to"]].name for h in hops]
        return {"ok": ok, "reason": reason, "hops": hops, "path": path,
                "source": src.name, "target": dst.name,
                "source_id": src_id, "target_id": dst_id}

    def dropped(reason: str) -> dict:
        # a host still hands the packet to its nearest router, which drops it
        hops = None if src.device_type == "router" else layer2(
            src_id, lambda d: devices[d].device_type == "router")
        return result(False, reason, hops or [])

    for d in (src, dst):
        if d.device_type == "switch":
            return result(False, f"{d.name} is a Layer 2 switch - it has no IP address to ping.", [])
    src_ip, dst_ip = _packet_ip(db, src), _packet_ip(db, dst)
    if not src_ip:
        return result(False, f"{src.name} has no IP address.", [])
    if not dst_ip:
        return dropped(f"{dst.name} has no IP address.")

    verdict = simulate_reachability(db, src_ip, dst_ip)
    if not verdict["ok"]:
        return dropped(verdict["reason"])

    hops: list[dict] = []
    at = src_id
    for stop in verdict.get("via_ids", []) + [dst_id]:
        if stop == at:
            continue
        leg = layer2(at, lambda d, stop=stop: d == stop)
        if leg is None:
            return result(False, f"No cable path from {devices[at].name} to {devices[stop].name}.", hops)
        hops += leg
        at = stop
    return result(True, verdict["reason"], hops)


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
