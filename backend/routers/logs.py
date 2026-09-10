from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from auth_utils import get_current_user
from database import get_db
from models import Log
from schemas import LogOut

router = APIRouter(prefix="/api/logs", tags=["logs"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[LogOut])
def list_logs(
    db: Session = Depends(get_db),
    category: str | None = Query(None, description="config | error | deploy | auth | system"),
    level: str | None = Query(None, description="info | warning | error"),
    limit: int = Query(200, le=1000),
):
    q = db.query(Log)
    if category:
        q = q.filter(Log.category == category)
    if level:
        q = q.filter(Log.level == level)
    return q.order_by(Log.timestamp.desc()).limit(limit).all()
