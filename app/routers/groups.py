from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..db import get_session
from ..models.db_models import Group, GroupMember, User, Session as SessionModel
from ..models.schemas import GroupCreate, GroupOut, GroupMemberOut, SessionCreate, SessionOut
from ..auth import get_current_user

router = APIRouter(prefix="/groups", tags=["groups"])


@router.post("", response_model=GroupOut, status_code=201)
def create_group(
    body: GroupCreate,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    group = Group(name=body.name, creator_id=current.id)
    db.add(group)
    db.flush()
    member = GroupMember(group_id=group.id, user_id=current.id)
    db.add(member)
    db.commit()
    db.refresh(group)
    return _group_out(group, db)


@router.get("/{group_id}", response_model=GroupOut)
def get_group(
    group_id: str,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    group = _get_or_404(group_id, db)
    _assert_member(group, current.id, db)
    return _group_out(group, db)


@router.get("/{group_id}/members", response_model=list[GroupMemberOut])
def list_members(
    group_id: str,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    group = _get_or_404(group_id, db)
    _assert_member(group, current.id, db)
    members = db.exec(select(GroupMember).where(GroupMember.group_id == group_id)).all()
    result = []
    for m in members:
        u = db.get(User, m.user_id)
        if u:
            result.append(GroupMemberOut(user_id=u.id, name=u.name, hue=u.hue))
    return result


@router.post("/{group_id}/join", response_model=GroupOut)
def join_group(
    group_id: str,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    """Join by group_id (used when opening invite link with the code)."""
    group = _get_or_404(group_id, db)
    already = db.exec(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == current.id,
        )
    ).first()
    if not already:
        db.add(GroupMember(group_id=group_id, user_id=current.id))
        db.commit()
    return _group_out(group, db)


@router.post("/join-by-code/{invite_code}", response_model=GroupOut)
def join_by_code(
    invite_code: str,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    group = db.exec(select(Group).where(Group.invite_code == invite_code.upper())).first()
    if not group:
        raise HTTPException(status_code=404, detail="Invalid invite code")
    already = db.exec(
        select(GroupMember).where(
            GroupMember.group_id == group.id,
            GroupMember.user_id == current.id,
        )
    ).first()
    if not already:
        db.add(GroupMember(group_id=group.id, user_id=current.id))
        db.commit()
    return _group_out(group, db)


# ---------- helpers ----------

def _get_or_404(group_id: str, db: Session) -> Group:
    g = db.get(Group, group_id)
    if not g:
        raise HTTPException(status_code=404, detail="Group not found")
    return g


def _assert_member(group: Group, user_id: str, db: Session) -> None:
    m = db.exec(
        select(GroupMember).where(
            GroupMember.group_id == group.id,
            GroupMember.user_id == user_id,
        )
    ).first()
    if not m:
        raise HTTPException(status_code=403, detail="Not a member of this group")


def _group_out(group: Group, db: Session) -> GroupOut:
    members = db.exec(select(GroupMember).where(GroupMember.group_id == group.id)).all()
    return GroupOut(
        id=group.id,
        name=group.name,
        creator_id=group.creator_id,
        invite_code=group.invite_code,
        member_count=len(members),
        session_id=group.session_id,
    )
