from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from ..db import get_session
from ..models.db_models import User
from ..models.schemas import RegisterIn, LoginIn, TokenOut, UserOut, PairIn
from ..auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut, status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_session)):
    existing = db.exec(select(User).where(User.email == body.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        name=body.name,
        email=body.email,
        hashed_password=hash_password(body.password),
        hue=body.hue,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenOut(
        access_token=create_access_token(user.id),
        user_id=user.id,
        name=user.name,
        email=user.email,
        hue=user.hue,
        partner_id=user.partner_id,
    )


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_session)):
    user = db.exec(select(User).where(User.email == body.email)).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return TokenOut(
        access_token=create_access_token(user.id),
        user_id=user.id,
        name=user.name,
        email=user.email,
        hue=user.hue,
        partner_id=user.partner_id,
    )


@router.get("/me", response_model=UserOut)
def me(current: User = Depends(get_current_user)):
    return UserOut(
        id=current.id,
        name=current.name,
        email=current.email,
        hue=current.hue,
        partner_id=current.partner_id,
    )


@router.post("/pair", response_model=UserOut)
def pair_with_partner(
    body: PairIn,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    partner = db.exec(select(User).where(User.email == body.partner_email)).first()
    if not partner:
        raise HTTPException(status_code=404, detail="No user with that email")
    if partner.id == current.id:
        raise HTTPException(status_code=400, detail="Cannot pair with yourself")
    current.partner_id = partner.id
    partner.partner_id = current.id
    db.add(current)
    db.add(partner)
    db.commit()
    db.refresh(current)
    return UserOut(
        id=current.id,
        name=current.name,
        email=current.email,
        hue=current.hue,
        partner_id=current.partner_id,
    )
