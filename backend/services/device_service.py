"""Device CRUD + status checks."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

import ipaddress

from models import Connection, Device, Interface, Routing, Vlan
from schemas import DeviceCreate, DeviceUpdate, ExtraIp
from services.deployment_service import tcp_ping

MANUAL_DESC = "manual"


def _prefix(mask: str | None) -> str:
    if not mask:
        return ""
    try:
        return "/" + str(ipaddress.ip_network(f"0.0.0.0/{mask}").prefixlen)
    except ValueError:
        return ""


def _parse_address(text: str) -> tuple[str, str]:
    """'10.0.5.1/24' or '10.0.5.1 255.255.255.0' -> ('10.0.5.1', '255.255.255.0')."""
    text = text.strip().replace("  ", " ")
    if "/" in text:
        net = ipaddress.ip_interface(text)
        return str(net.ip), str(net.netmask)
    parts = text.split()
    if len(parts) == 2:
        ipaddress.ip_address(parts[0])
        ipaddress.ip_address(parts[1])
        return parts[0], parts[1]
    ipaddress.ip_address(text)                 # bare IP -> assume /24
    return text, "255.255.255.0"


def _apply_extra_ips(db: Session, device: Device, extras: list[ExtraIp]) -> None:
    """Replace the device's hand-entered interface IPs with `extras`."""
    db.query(Interface).filter(
        Interface.device_id == device.id, Interface.description == MANUAL_DESC
    ).delete()
    for e in extras:
        if not e.interface.strip() or not e.address.strip():
            continue
        try:
            ip, mask = _parse_address(e.address)
        except ValueError:
            raise ValueError(f"'{e.address}' is not a valid IP address.")
        row = (
            db.query(Interface)
            .filter(Interface.device_id == device.id, Interface.name == e.interface.strip())
            .first()
        )
        if row is not None:      # an auto-generated interface already uses this name
            row.ip_address, row.subnet_mask, row.description = ip, mask, MANUAL_DESC
        else:
            db.add(Interface(
                device_id=device.id, name=e.interface.strip(), ip_address=ip,
                subnet_mask=mask, mode="routed", description=MANUAL_DESC, enabled=True,
            ))


def attach_ips(db: Session, devices: list[Device]) -> list[Device]:
    """Populate each device's `ip_addresses` (interface IPs + mgmt) for the API."""
    ifaces: dict[int, list[dict]] = {}
    for i in db.query(Interface).filter(Interface.ip_address.isnot(None)).all():
        desc = (i.description or "").lower()
        role = ("lan" if desc.startswith("lan")
                else "link" if desc.startswith(("link", "point-to-point"))
                else "manual" if desc == MANUAL_DESC
                else "iface")
        ifaces.setdefault(i.device_id, []).append({
            "interface": i.name,
            "ip": f"{i.ip_address}{_prefix(i.subnet_mask)}",
            "role": role,
        })
    for d in devices:
        rows = list(ifaces.get(d.id, []))
        if d.mgmt_ip and not any(r["ip"].split("/")[0] == d.mgmt_ip for r in rows):
            rows.insert(0, {"interface": "mgmt", "ip": d.mgmt_ip, "role": "mgmt"})
        d.ip_addresses = rows
    return devices


def list_devices(db: Session) -> list[Device]:
    return db.query(Device).order_by(Device.id).all()


def get_device(db: Session, device_id: int) -> Device | None:
    return db.get(Device, device_id)


# a switch never carries an IP, but it may keep SSH credentials so the generated
# config can show the SSH management block (username / vty / login local)
_SWITCH_CLEARED = ("mgmt_ip",)


def _enforce_switch_l2(device: Device) -> None:
    """A switch is pure Layer 2 in this platform: it never carries an IP."""
    if device.device_type == "switch":
        for field in _SWITCH_CLEARED:
            setattr(device, field, None)


def create_device(db: Session, data: DeviceCreate) -> Device:
    payload = data.model_dump(exclude={"extra_ips"})
    device = Device(**payload)
    _enforce_switch_l2(device)
    db.add(device)
    db.commit()
    db.refresh(device)
    if data.extra_ips and device.device_type != "switch":
        _apply_extra_ips(db, device, data.extra_ips)
        db.commit()
    return device


def update_device(db: Session, device: Device, data: DeviceUpdate) -> Device:
    fields = data.model_dump(exclude_unset=True, exclude={"extra_ips"})
    ip_changed = (
        "mgmt_ip" in fields and fields["mgmt_ip"] != device.mgmt_ip
        and device.device_type == "router"
    )
    for key, value in fields.items():
        setattr(device, key, value)
    _enforce_switch_l2(device)

    if ip_changed:
        # auto-generated interfaces were derived from the old address - drop them
        # so nothing stale is shown; hand-entered ("manual") ones are kept
        for i in db.query(Interface).filter(Interface.device_id == device.id).all():
            if (i.description or "").lower() != MANUAL_DESC:
                db.delete(i)
        db.query(Routing).filter(Routing.device_id == device.id).delete()
        db.query(Vlan).filter(Vlan.device_id == device.id).delete()
        device.last_config = None

    if data.extra_ips is not None and device.device_type != "switch":
        _apply_extra_ips(db, device, data.extra_ips)

    db.commit()
    db.refresh(device)
    return device


def delete_device(db: Session, device: Device) -> None:
    db.query(Connection).filter(
        (Connection.a_device_id == device.id) | (Connection.b_device_id == device.id)
    ).delete(synchronize_session=False)
    db.delete(device)
    db.commit()


def _has_link(db: Session, device_id: int) -> bool:
    return (
        db.query(Connection)
        .filter((Connection.a_device_id == device_id) | (Connection.b_device_id == device_id))
        .count()
        > 0
    )


def refresh_status(db: Session, device: Device) -> Device:
    # 1) real probe (works with GNS3/EVE-NG);  2) otherwise a device that is
    # cabled in the topology counts as "online" (design-level status).
    reachable = tcp_ping(device.mgmt_ip or "", port=22) or _has_link(db, device.id)
    device.status = "online" if reachable else "offline"
    device.last_checked = datetime.now(timezone.utc)
    db.commit()
    db.refresh(device)
    return device


def refresh_all_status(db: Session) -> list[Device]:
    devices = list_devices(db)
    for d in devices:
        refresh_status(db, d)
    return devices
