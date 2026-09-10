from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth_utils import get_current_user
from database import get_db
from models import Device, Log, Vlan
from schemas import DashboardOut

router = APIRouter(
    prefix="/api/dashboard", tags=["dashboard"], dependencies=[Depends(get_current_user)]
)


@router.get("", response_model=DashboardOut)
def summary(db: Session = Depends(get_db)):
    devices = db.query(Device).all()
    by_type = {"router": 0, "switch": 0, "pc": 0, "ip_phone": 0, "printer": 0, "server": 0}
    online = offline = 0
    for d in devices:
        by_type[d.device_type] = by_type.get(d.device_type, 0) + 1
        if d.status == "online":
            online += 1
        elif d.status == "offline":
            offline += 1

    recent = (
        db.query(Log)
        .filter(Log.category.in_(["deploy", "config"]))
        .order_by(Log.timestamp.desc())
        .limit(10)
        .all()
    )
    return DashboardOut(
        total_devices=len(devices),
        online_devices=online,
        offline_devices=offline,
        total_vlans=db.query(Vlan).count(),
        routers=by_type.get("router", 0),
        switches=by_type.get("switch", 0),
        pcs=by_type.get("pc", 0),
        ip_phones=by_type.get("ip_phone", 0),
        printers=by_type.get("printer", 0),
        servers=by_type.get("server", 0),
        recent_deploys=recent,
    )
