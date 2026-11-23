"""Topology graph: nodes (devices) + edges (connections)."""
from __future__ import annotations

import ipaddress

from sqlalchemy.orm import Session

from models import Connection, Device, Interface, Vlan


def get_graph(db: Session) -> dict:
    devices = db.query(Device).order_by(Device.id).all()
    conns = db.query(Connection).order_by(Connection.id).all()
    return {
        "nodes": [
            {
                "id": d.id,
                "name": d.name,
                "hostname": d.hostname,
                "type": d.device_type,
                "status": d.status,
                "x": d.pos_x,
                "y": d.pos_y,
            }
            for d in devices
        ],
        "edges": [
            {
                "id": c.id,
                "source": c.a_device_id,
                "target": c.b_device_id,
                "source_interface": c.a_interface,
                "target_interface": c.b_interface,
                "link_type": c.link_type,
                "status": c.status,
            }
            for c in conns
        ],
    }


def port_name(name: str | None) -> str:
    """Full port name, however it was stored (Gi0/1 -> GigabitEthernet0/1)."""
    name = name or ""
    for short, full in (("Gi", "GigabitEthernet"), ("Fa", "FastEthernet")):
        if name.startswith(short) and name[2:3].isdigit():
            return full + name[2:]
    return name


def device_info(db: Session, device_id: int) -> dict | None:
    """Port table of one device (the topology's hover box): link, VLAN, IP."""
    device = db.get(Device, device_id)
    if device is None:
        return None

    def ends(d: Device) -> dict[str, tuple[Device, str]]:
        """port -> (device, port) on the other end of its cable"""
        out: dict[str, tuple[Device, str]] = {}
        for c in db.query(Connection).filter(
            (Connection.a_device_id == d.id) | (Connection.b_device_id == d.id)
        ).order_by(Connection.id):
            mine, peer, theirs = (
                (c.a_interface, c.b_device, c.b_interface) if c.a_device_id == d.id
                else (c.b_interface, c.a_device, c.a_interface)
            )
            if peer is not None and c.status != "down":
                out.setdefault(port_name(mine), (peer, port_name(theirs)))
        return out

    def interfaces(d: Device) -> dict[str, Interface]:
        return {port_name(i.name): i for i in db.query(Interface).filter(Interface.device_id == d.id)}

    def net_of(i: Interface):
        try:
            return ipaddress.ip_network(f"{i.ip_address}/{i.subnet_mask}", strict=False)
        except ValueError:
            return None

    def vlan_of(d: Device, port: str) -> int | None:
        row = interfaces(d).get(port)
        vlans = db.query(Vlan).filter(Vlan.device_id == d.id).all()
        if d.device_type == "switch":
            if row is not None and row.mode == "trunk":
                return None
            if row is not None and row.vlan_id:
                return row.vlan_id
            # Smart Auto puts every cabled port and the FastEthernet range in the
            # LAN's VLAN; any other port stays in the default VLAN 1
            lan = [v for v in vlans if v.subnet]
            return lan[0].vlan_id if len(lan) == 1 and (port in ends(d) or port.startswith("Fast")) else 1
        if d.device_type == "router":
            net = net_of(row) if row is not None and row.ip_address else None
            return next((v.vlan_id for v in vlans if net and v.subnet == str(net)), None)
        return None

    cables, rows = ends(device), interfaces(device)
    ports = []
    if device.device_type in ("router", "switch"):
        for name in {p for p in (*cables, *rows) if p}:
            i = rows.get(name)
            net = net_of(i) if i is not None and i.ip_address else None
            ports.append({
                "port": name,
                "link": "Up" if name in cables and (i is None or i.enabled is not False) else "Down",
                "vlan": vlan_of(device, name),
                "ip": (f"{i.ip_address}/{net.prefixlen}" if net else i.ip_address) if i is not None else None,
            })
        if device.mgmt_ip and not any((p["ip"] or "").split("/")[0] == device.mgmt_ip for p in ports):
            ports.append({"port": "Management", "link": None, "vlan": None, "ip": device.mgmt_ip})
    else:
        # a host has one address; it takes the mask of the router LAN it sits in
        ip = device.mgmt_ip
        if ip:
            for i in db.query(Interface).filter(Interface.ip_address.isnot(None)):
                net = net_of(i)
                if net and i.device_id != device.id and ipaddress.ip_address(ip) in net:
                    ip = f"{ip}/{net.prefixlen}"
                    break
        names = sorted(p for p in cables if p) or ["eth0"]
        for n, name in enumerate(names):
            peer = cables.get(name)
            ports.append({
                "port": name, "link": "Up" if peer else "Down",
                "vlan": vlan_of(*peer) if peer else None, "ip": ip if n == 0 else None,
            })
    return {"id": device.id, "name": device.name, "hostname": device.hostname,
            "type": device.device_type, "ports": sorted(ports, key=lambda p: p["port"]),
            # VLAN of a switch's FastEthernet ports that nothing uses yet
            "spare_vlan": vlan_of(device, "FastEthernet")}


def create_connection(
    db: Session,
    a_id: int,
    b_id: int,
    a_iface: str | None,
    b_iface: str | None,
    link_type: str,
) -> Connection:
    if a_id == b_id:
        raise ValueError("Cannot connect a device to itself.")
    for did in (a_id, b_id):
        if db.get(Device, did) is None:
            raise ValueError(f"Device {did} does not exist.")
    # router/switch to router/switch cables are always access links
    if all(db.get(Device, did).device_type in ("router", "switch") for did in (a_id, b_id)):
        link_type = "access"
    conn = Connection(
        a_device_id=a_id,
        b_device_id=b_id,
        a_interface=a_iface,
        b_interface=b_iface,
        link_type=link_type,
    )
    db.add(conn)
    # a cabled device is "online" in the design view
    for did in (a_id, b_id):
        d = db.get(Device, did)
        if d:
            d.status = "online"
    db.commit()
    db.refresh(conn)
    return conn


def delete_connection(db: Session, conn_id: int) -> bool:
    conn = db.get(Connection, conn_id)
    if conn is None:
        return False
    endpoints = (conn.a_device_id, conn.b_device_id)
    db.delete(conn)
    db.commit()
    for did in endpoints:
        still_linked = (
            db.query(Connection)
            .filter((Connection.a_device_id == did) | (Connection.b_device_id == did))
            .count()
            > 0
        )
        d = db.get(Device, did)
        if d and not still_linked:
            d.status = "offline"
    db.commit()
    return True


def move_device(db: Session, device_id: int, x: float, y: float) -> Device | None:
    device = db.get(Device, device_id)
    if device is None:
        return None
    device.pos_x = x
    device.pos_y = y
    db.commit()
    db.refresh(device)
    return device
