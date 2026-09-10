"""DHCP for PCs — hand out an address from a router LAN's pool, on demand."""
from __future__ import annotations

import ipaddress

from sqlalchemy.orm import Session

from models import ENDPOINT_TYPES, Connection, Device, Interface, Vlan
from services.logging_service import write_log


def _pool(subnet: str, gateway: str) -> list[str]:
    net = ipaddress.ip_network(subnet, strict=False)
    gw = int(ipaddress.ip_address(gateway))
    return [str(h) for h in net.hosts() if int(h) > gw]


def _used_ips(db: Session) -> set[str]:
    return {d.mgmt_ip for d in db.query(Device).all() if d.mgmt_ip}


def _router_scopes(db: Session) -> list[Vlan]:
    """One Vlan row per router LAN that has a subnet + gateway."""
    router_ids = {d.id for d in db.query(Device).filter(Device.device_type == "router").all()}
    seen: set[str] = set()
    rows: list[Vlan] = []
    for v in db.query(Vlan).order_by(Vlan.id).all():
        if v.device_id in router_ids and v.subnet and v.gateway and v.subnet not in seen:
            seen.add(v.subnet)
            rows.append(v)
    return rows


def list_scopes(db: Session) -> list[dict]:
    taken = _used_ips(db)
    hostnames = {d.id: d.hostname for d in db.query(Device).all()}
    out = []
    for v in _router_scopes(db):
        pool = _pool(v.subnet, v.gateway)
        out.append({
            "subnet": v.subnet,                       # <- the real identifier
            "vlan_id": v.vlan_id,
            "router": hostnames.get(v.device_id, "?"),
            "name": v.name or f"VLAN {v.vlan_id}",
            "gateway": v.gateway,
            "free": sum(1 for ip in pool if ip not in taken),
            "size": len(pool),
        })
    return out


def _detect_subnet(db: Session, pc: Device) -> str | None:
    """Follow the PC's cable to a router LAN and return that LAN's subnet."""
    scope_subnets = {v.subnet for v in _router_scopes(db)}
    seen = {pc.id}
    stack = [pc.id]
    while stack:
        cur = stack.pop()
        for c in db.query(Connection).filter(
            (Connection.a_device_id == cur) | (Connection.b_device_id == cur)
        ).all():
            peer_id = c.b_device_id if c.a_device_id == cur else c.a_device_id
            if peer_id in seen:
                continue
            peer = db.get(Device, peer_id)
            if peer is None:
                continue
            if peer.device_type == "router":
                for v in _router_scopes(db):
                    if v.device_id == peer.id:
                        return v.subnet
                return next(iter(scope_subnets), None)
            seen.add(peer_id)
            stack.append(peer_id)           # keep walking through switches
    return None


def assign(db: Session, pc: Device, subnet: str | None = None,
           vlan_id: int | None = None) -> dict:
    if pc.device_type not in ENDPOINT_TYPES:
        raise ValueError("Only hosts (PC / IP phone / printer) obtain an address via DHCP.")

    scopes = {s["subnet"]: s for s in list_scopes(db)}
    if not scopes:
        raise ValueError("No DHCP scope exists. Run Smart Auto Config first.")

    if subnet is None and vlan_id is not None:
        subnet = next((s["subnet"] for s in scopes.values() if s["vlan_id"] == vlan_id), None)
    if subnet is None:
        subnet = _detect_subnet(db, pc)
    if subnet is None:
        raise ValueError(
            "Could not detect the PC's network — connect it to a switch/router in "
            "the topology, or pick a network."
        )
    if subnet not in scopes:
        raise ValueError(f"{subnet} is not a DHCP scope on any router.")

    row = next(v for v in _router_scopes(db) if v.subnet == subnet)
    taken = _used_ips(db)
    free = next((ip for ip in _pool(row.subnet, row.gateway) if ip not in taken), None)
    if free is None:
        raise ValueError(f"DHCP pool for {subnet} is exhausted.")

    pc.mgmt_ip = free
    pc.status = "online"
    db.commit()
    db.refresh(pc)
    write_log(
        db,
        f"{pc.hostname} obtained {free} via DHCP "
        f"({row.subnet}, VLAN {row.vlan_id}, gw {row.gateway})",
        category="deploy",
        device_id=pc.id,
    )
    return {
        "ip": free, "subnet": row.subnet, "vlan_id": row.vlan_id,
        "gateway": row.gateway, "name": row.name,
    }


def release(db: Session, pc: Device) -> None:
    old = pc.mgmt_ip
    pc.mgmt_ip = None
    db.commit()
    if old:
        write_log(db, f"{pc.hostname} released DHCP address {old}",
                  category="deploy", device_id=pc.id)
