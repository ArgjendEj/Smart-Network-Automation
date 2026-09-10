"""Topology graph: nodes (devices) + edges (connections)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from models import Connection, Device


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
