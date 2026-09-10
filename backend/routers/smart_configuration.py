from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth_utils import get_current_user
from database import get_db
from schemas import SmartConfigIn, SmartConfigResult
from models import Device
from services import auto_topology_service, smart_config_service
from services.smart_config_service import (
    _IfaceAllocator,
    ROUTER_UPLINK,
    allocate_access_ports,
    build_p2p_links,
)
from services.subnet_calculator import plan_departments

router = APIRouter(
    prefix="/api/smart-config", tags=["smart-config"], dependencies=[Depends(get_current_user)]
)


@router.post("/preview")
def preview(payload: SmartConfigIn, db: Session = Depends(get_db)):
    """Return the subnet/VLAN/IP plan without generating or deploying anything."""
    try:
        plan = plan_departments([(d.name, d.users) for d in payload.departments])
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    out = plan.as_dict()
    out["access_ports"] = allocate_access_ports(plan)

    router = db.get(Device, payload.router_id)
    peers = [db.get(Device, pid) for pid in payload.peer_router_ids]
    peers = [p for p in peers if p and p.device_type == "router" and p.id != payload.router_id]
    if router and peers:
        alloc = _IfaceAllocator()
        if plan.departments:
            alloc.reserve(router.id, ROUTER_UPLINK)
        out["router_links"] = [
            {
                "a": router.hostname, "a_if": link["local_if"], "a_ip": link["local_ip"],
                "b": link["peer_hostname"], "b_if": link["peer_if"], "b_ip": link["peer_ip"],
                "subnet": link["cidr"],
            }
            for link in build_p2p_links(router, peers, alloc)
        ]
    return out


@router.post("/run", response_model=SmartConfigResult)
def run(payload: SmartConfigIn, db: Session = Depends(get_db)):
    try:
        return smart_config_service.run(db, payload)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


class AutoIn(BaseModel):
    scope: Literal["all", "lan", "wan"] = "all"
    routing: Literal["ospf", "bgp", "both"] = "ospf"
    nat: bool = False


@router.post("/auto")
def auto(payload: AutoIn | None = None, db: Session = Depends(get_db)):
    """Topology-driven config.
    scope='wan' -> only router-to-router links; 'lan' -> only local networks + DHCP.
    routing='bgp' -> eBGP between routers instead of OSPF.
    nat=True -> NAT overload (PAT) on each router: its LANs as inside, its first
    router-to-router link as outside.
    """
    p = payload or AutoIn()
    try:
        return auto_topology_service.run(db, p.scope, p.routing, p.nat)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
