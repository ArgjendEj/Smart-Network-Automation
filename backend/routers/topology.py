from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth_utils import get_current_user
from database import get_db
from schemas import ConnectionCreate, ConnectionOut
from services import topology_service
from services.logging_service import write_log

router = APIRouter(
    prefix="/api/topology", tags=["topology"], dependencies=[Depends(get_current_user)]
)


class MoveIn(BaseModel):
    x: float
    y: float


@router.get("")
def graph(db: Session = Depends(get_db)):
    return topology_service.get_graph(db)


@router.post("/connections", response_model=ConnectionOut, status_code=201)
def add_connection(data: ConnectionCreate, db: Session = Depends(get_db)):
    try:
        conn = topology_service.create_connection(
            db, data.a_device_id, data.b_device_id, data.a_interface, data.b_interface, data.link_type
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    write_log(db, f"Link created ({data.a_device_id}<->{data.b_device_id})", category="config")
    return conn


@router.delete("/connections/{conn_id}", status_code=204)
def remove_connection(conn_id: int, db: Session = Depends(get_db)):
    if not topology_service.delete_connection(db, conn_id):
        raise HTTPException(404, "Connection not found")
    write_log(db, f"Link {conn_id} deleted", level="warning", category="config")


@router.patch("/devices/{device_id}/position")
def move(device_id: int, data: MoveIn, db: Session = Depends(get_db)):
    device = topology_service.move_device(db, device_id, data.x, data.y)
    if device is None:
        raise HTTPException(404, "Device not found")
    return {"id": device.id, "x": device.pos_x, "y": device.pos_y}
