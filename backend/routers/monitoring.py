from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth_utils import get_current_user
from database import get_db
from models import Device, Interface, Vlan
from services import monitoring_service
from services.logging_service import write_log

router = APIRouter(
    prefix="/api/monitoring", tags=["monitoring"], dependencies=[Depends(get_current_user)]
)


class PingIn(BaseModel):
    target: str
    mode: Literal["design", "server", "device"] = "design"
    source_device_id: Optional[int] = None   # for mode="device"
    source_ip: Optional[str] = None          # for mode="design"
    count: int = 5


class PacketIn(BaseModel):
    source_device_id: int
    target_device_id: int


@router.post("/packet")
def packet(data: PacketIn, db: Session = Depends(get_db)):
    """One envelope between two devices - verdict + the cables it crosses."""
    try:
        result = monitoring_service.trace_packet(db, data.source_device_id, data.target_device_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    write_log(
        db,
        f"[packet] {result['source']} -> {result['target']}: "
        f"{'Successful' if result['ok'] else 'Failed'}",
        level="info" if result["ok"] else "warning",
        category="system",
        device_id=data.source_device_id,
        detail=f"{' -> '.join(result['path'])} | {result['reason']}",
    )
    return result


@router.get("/endpoints")
def endpoints(db: Session = Depends(get_db)):
    """Every IP actually assigned in the design — the only valid ping sources/targets."""
    out: list[dict] = []
    dev_name = {d.id: d.hostname for d in db.query(Device).all()}

    for d in db.query(Device).filter(Device.mgmt_ip.isnot(None)).all():
        out.append({"ip": d.mgmt_ip, "label": f"{d.hostname} ({d.device_type})", "kind": "device"})

    for i in db.query(Interface).filter(Interface.ip_address.isnot(None)).all():
        out.append({
            "ip": i.ip_address,
            "label": f"{dev_name.get(i.device_id, '?')} {i.name}",
            "kind": "router-interface",
        })

    for v in db.query(Vlan).filter(Vlan.gateway.isnot(None)).all():
        out.append({
            "ip": v.gateway,
            "label": f"{v.department or ('VLAN ' + str(v.vlan_id))} gateway",
            "kind": "gateway",
        })

    seen, uniq = set(), []
    for e in out:
        if e["ip"] in seen:
            continue
        seen.add(e["ip"])
        uniq.append(e)
    return uniq


def _guess_source_ip(db: Session, device_id: int) -> Optional[str]:
    row = (
        db.query(Interface)
        .filter(Interface.device_id == device_id, Interface.ip_address.isnot(None))
        .first()
    )
    if row:
        return row.ip_address
    v = db.query(Vlan).filter(Vlan.device_id == device_id, Vlan.gateway.isnot(None)).first()
    return v.gateway if v else None


@router.post("/ping")
def ping(data: PingIn, db: Session = Depends(get_db)):
    if data.mode == "design":
        source = data.source_ip
        if source is None and data.source_device_id is not None:
            source = _guess_source_ip(db, data.source_device_id)
        if not source:
            raise HTTPException(400, "design mode needs source_ip (or a device with a configured IP)")
        result = monitoring_service.simulate_reachability(db, source, data.target)
        result.setdefault("loss_pct", 0 if result["ok"] else 100)
        result["output"] = result.get("reason", "")
        src_label = source

    elif data.mode == "server":
        result = monitoring_service.ping_from_server(data.target, data.count)
        src_label = "server"

    else:  # device
        if data.source_device_id is None:
            raise HTTPException(400, "device mode needs source_device_id")
        device = db.get(Device, data.source_device_id)
        if device is None:
            raise HTTPException(404, "source device not found")
        result = monitoring_service.ping_from_device(device, data.target, data.count)
        src_label = device.hostname

    write_log(
        db,
        f"[{data.mode}] ping {src_label} -> {data.target}: "
        f"{'OK' if result['ok'] else 'FAIL'} ({result['loss_pct']}% loss)",
        level="info" if result["ok"] else "warning",
        category="system",
        device_id=data.source_device_id,
        detail=result.get("output", "")[:2000],
    )
    return {"mode": data.mode, "source": src_label, "target": data.target, **result}
