from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from auth_utils import create_access_token, get_current_user, hash_password, verify_password
from database import get_db
from models import User
from schemas import RegisterIn, Token, UserOut
from services.logging_service import write_log

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    username = data.username.strip()
    if db.query(User).filter(User.username == username).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That username is already taken."
        )
    user = User(username=username, hashed_password=hash_password(data.password), role="admin")
    db.add(user)
    db.commit()
    write_log(db, f"New account registered: '{username}'", level="info", category="auth")
    return Token(access_token=create_access_token(user.username))


@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form.username).first()
    if user is None or not verify_password(form.password, user.hashed_password):
        write_log(db, f"Failed login for '{form.username}'", level="warning", category="auth")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password"
        )
    write_log(db, f"User '{user.username}' logged in", level="info", category="auth")
    return Token(access_token=create_access_token(user.username))


@router.post("/logout")
def logout(current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    write_log(db, f"User '{current.username}' logged out", level="info", category="auth")
    return {"detail": "logged out"}


@router.get("/me", response_model=UserOut)
def me(current: User = Depends(get_current_user)):
    return current
