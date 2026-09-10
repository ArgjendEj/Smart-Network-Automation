from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth_utils import get_current_user
from database import get_db
from schemas import ConfigResult, ManualConfigIn
from services import manual_config_service

router = APIRouter(
    prefix="/api/manual-config", tags=["manual-config"], dependencies=[Depends(get_current_user)]
)


@router.post("/run", response_model=ConfigResult)
def run(payload: ManualConfigIn, db: Session = Depends(get_db)):
    try:
        return manual_config_service.run(db, payload)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
