import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from ..db import get_session
from ..models.db_models import User, SwipeRecord, QueueItem, Match
from ..models.schemas import (
    RegisterIn, LoginIn, TokenOut, UserOut, PairIn,
    InviteOut, PairByTokenIn, DeleteAccountIn, UpdateThemeIn,
)
from ..auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

APP_URL = "https://watchmatch.crig.dev"


@router.post("/register", response_model=TokenOut, status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_session)):
    existing = db.exec(select(User).where(User.email == body.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    if len(body.password) < 6:
        raise HTTPException(status_code=422, detail="Password must be at least 6 characters")
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
        theme=user.theme,
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
        theme=user.theme,
    )


@router.get("/me", response_model=UserOut)
def me(current: User = Depends(get_current_user)):
    return UserOut(
        id=current.id,
        name=current.name,
        email=current.email,
        hue=current.hue,
        partner_id=current.partner_id,
        theme=current.theme,
    )


@router.patch("/me/theme", response_model=UserOut)
def update_theme(
    body: UpdateThemeIn,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    current.theme = body.theme
    db.add(current)
    db.commit()
    db.refresh(current)
    return UserOut(
        id=current.id,
        name=current.name,
        email=current.email,
        hue=current.hue,
        partner_id=current.partner_id,
        theme=current.theme,
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
        theme=current.theme,
    )


@router.post("/invite", response_model=InviteOut)
def generate_invite(
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    """Generate a one-time invite link. Anyone who opens it and is logged in gets paired."""
    token = uuid.uuid4().hex[:10]
    current.invite_token = token
    db.add(current)
    db.commit()
    return InviteOut(token=token, url=f"{APP_URL}/auth/pair?token={token}")


@router.post("/pair-by-token", response_model=UserOut)
def pair_by_token(
    body: PairByTokenIn,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    """Pair the current user with whoever generated the given invite token."""
    partner = db.exec(select(User).where(User.invite_token == body.token)).first()
    if not partner:
        raise HTTPException(status_code=404, detail="Invite link is invalid or expired")
    if partner.id == current.id:
        raise HTTPException(status_code=400, detail="Cannot pair with yourself")
    current.partner_id = partner.id
    partner.partner_id = current.id
    partner.invite_token = None  # invalidate after use
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
        theme=current.theme,
    )


@router.delete("/me", status_code=204)
def delete_account(
    body: DeleteAccountIn,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    """Permanently delete the account and all associated data."""
    if not verify_password(body.password, current.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect password")

    # Remove from partner's partner_id
    if current.partner_id:
        partner = db.get(User, current.partner_id)
        if partner and partner.partner_id == current.id:
            partner.partner_id = None
            db.add(partner)

    # Delete owned data
    for record in db.exec(select(SwipeRecord).where(SwipeRecord.user_id == current.id)).all():
        db.delete(record)
    for item in db.exec(select(QueueItem).where(QueueItem.user_id == current.id)).all():
        db.delete(item)

    db.delete(current)
    db.commit()
