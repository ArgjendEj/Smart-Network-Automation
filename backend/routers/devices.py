from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth_utils import get_current_user
from database import get_db
from models import Interface, Routing, User, Vlan
from schemas import (
    DeviceCreate,
    DeviceOut,
    DeviceUpdate,
    InterfaceOut,
    RoutingOut,
    VlanOut,
)
from services import device_service, dhcp_service
from services.logging_service import write_log

router = APIRouter(prefix="/api/devices", tags=["devices"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[DeviceOut])
def list_all(db: Session = Depends(get_db)):
    return device_service.attach_ips(db, device_service.list_devices(db))


@router.post("", response_model=DeviceOut, status_code=201)
def create(data: DeviceCreate, db: Session = Depends(get_db)):
    device = device_service.create_device(db, data)
    write_log(db, f"Device '{device.name}' added", category="config", device_id=device.id)
    return device


@router.get("/{device_id}", response_model=DeviceOut)
def detail(device_id: int, db: Session = Depends(get_db)):
    device = device_service.get_device(db, device_id)
    if device is None:
        raise HTTPException(404, "Device not found")
    return device_service.attach_ips(db, [device])[0]


@router.put("/{device_id}", response_model=DeviceOut)
def update(device_id: int, data: DeviceUpdate, db: Session = Depends(get_db)):
    device = device_service.get_device(db, device_id)
    if device is None:
        raise HTTPException(404, "Device not found")
    try:
        device = device_service.update_device(db, device, data)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(400, str(exc))
    write_log(db, f"Device '{device.name}' edited", category="config", device_id=device.id)
    return device


@router.delete("/{device_id}", status_code=204)
def delete(device_id: int, db: Session = Depends(get_db)):
    device = device_service.get_device(db, device_id)
    if device is None:
        raise HTTPException(404, "Device not found")
    name = device.name
    device_service.delete_device(db, device)
    write_log(db, f"Device '{name}' deleted", level="warning", category="config")


@router.post("/status/refresh-all", response_model=list[DeviceOut])
def refresh_all(db: Session = Depends(get_db)):
    return device_service.refresh_all_status(db)


@router.post("/{device_id}/status", response_model=DeviceOut)
def check_status(device_id: int, db: Session = Depends(get_db)):
    device = device_service.get_device(db, device_id)
    if device is None:
        raise HTTPException(404, "Device not found")
    return device_service.refresh_status(db, device)


@router.get("/{device_id}/interfaces", response_model=list[InterfaceOut])
def interfaces(device_id: int, db: Session = Depends(get_db)):
    return db.query(Interface).filter(Interface.device_id == device_id).order_by(Interface.name).all()


@router.get("/{device_id}/vlans", response_model=list[VlanOut])
def vlans(device_id: int, db: Session = Depends(get_db)):
    return db.query(Vlan).filter(Vlan.device_id == device_id).order_by(Vlan.vlan_id).all()


@router.get("/{device_id}/routing", response_model=list[RoutingOut])
def routing(device_id: int, db: Session = Depends(get_db)):
    return db.query(Routing).filter(Routing.device_id == device_id).all()


class DhcpIn(BaseModel):
    subnet: str | None = None       # e.g. "192.168.2.0/24" - the network to pull from
    vlan_id: int | None = None      # accepted for backwards compatibility


@router.get("/dhcp/scopes")
def dhcp_scopes(db: Session = Depends(get_db)):
    return dhcp_service.list_scopes(db)


@router.post("/{device_id}/dhcp", response_model=DeviceOut)
def request_dhcp(device_id: int, data: DhcpIn, db: Session = Depends(get_db)):
    device = device_service.get_device(db, device_id)
    if device is None:
        raise HTTPException(404, "Device not found")
    try:
        dhcp_service.assign(db, device, subnet=data.subnet, vlan_id=data.vlan_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return device


@router.delete("/{device_id}/dhcp", response_model=DeviceOut)
def release_dhcp(device_id: int, db: Session = Depends(get_db)):
    device = device_service.get_device(db, device_id)
    if device is None:
        raise HTTPException(404, "Device not found")
    dhcp_service.release(db, device)
    return device


@router.get("/{device_id}/config")
def last_config(device_id: int, db: Session = Depends(get_db)):
    device = device_service.get_device(db, device_id)
    if device is None:
        raise HTTPException(404, "Device not found")
    return {"device_id": device.id, "config": device.last_config or ""}
