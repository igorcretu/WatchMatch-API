from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..db import get_session
from ..models.db_models import User, QueueItem, Match, Movie, SwipeRecord
from ..models.schemas import UserOut, QueueItemOut, RateIn, MovieOut
from ..auth import get_current_user
from .movies import movie_to_out

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me/queue", response_model=list[QueueItemOut])
def get_queue(
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    items = db.exec(
        select(QueueItem).where(QueueItem.user_id == current.id, QueueItem.watched == False)
    ).all()
    return [_queue_item_out(item, db) for item in items]


@router.get("/me/history", response_model=list[QueueItemOut])
def get_history(
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    items = db.exec(
        select(QueueItem).where(QueueItem.user_id == current.id, QueueItem.watched == True)
    ).all()
    return [_queue_item_out(item, db) for item in items]


@router.patch("/me/queue/{movie_id}/watched", response_model=QueueItemOut)
def mark_watched(
    movie_id: str,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    item = db.exec(
        select(QueueItem).where(
            QueueItem.user_id == current.id,
            QueueItem.movie_id == movie_id,
        )
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Not in queue")
    item.watched = True
    db.add(item)
    db.commit()
    db.refresh(item)
    return _queue_item_out(item, db)


@router.patch("/me/history/{movie_id}/rate", response_model=QueueItemOut)
def rate_watched(
    movie_id: str,
    body: RateIn,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    if not (1 <= body.rating <= 5):
        raise HTTPException(status_code=422, detail="Rating must be 1–5")
    # Store rating on the Match row
    match = db.exec(
        select(Match).where(Match.movie_id == movie_id)
    ).first()
    if match:
        if match.session_id:
            from ..models.db_models import Session as S
            s = db.get(S, match.session_id)
            if s and s.user_id == current.id:
                match.user1_rating = body.rating
            else:
                match.user2_rating = body.rating
            db.add(match)
            db.commit()

    item = db.exec(
        select(QueueItem).where(
            QueueItem.user_id == current.id,
            QueueItem.movie_id == movie_id,
        )
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Not in history")
    return _queue_item_out(item, db)


@router.get("/me/disliked", response_model=list[MovieOut])
def get_disliked(
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    records = db.exec(
        select(SwipeRecord).where(
            SwipeRecord.user_id == current.id,
            SwipeRecord.action == "pass",
        )
    ).all()
    movies = [db.get(Movie, r.movie_id) for r in records]
    return [movie_to_out(m) for m in movies if m]


@router.delete("/me/disliked/{movie_id}", status_code=204)
def undo_dislike(
    movie_id: str,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    """Remove the pass record so the movie appears in future sessions."""
    record = db.exec(
        select(SwipeRecord).where(
            SwipeRecord.user_id == current.id,
            SwipeRecord.movie_id == movie_id,
            SwipeRecord.action == "pass",
        )
    ).first()
    if record:
        db.delete(record)
        db.commit()


@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: str,
    db: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut(
        id=user.id,
        name=user.name,
        email=user.email,
        hue=user.hue,
        partner_id=user.partner_id,
    )


def _queue_item_out(item: QueueItem, db: Session) -> QueueItemOut:
    movie = db.get(Movie, item.movie_id)
    if not movie:
        raise HTTPException(status_code=500, detail=f"Movie {item.movie_id} missing from DB")
    return QueueItemOut(
        id=item.id,
        movie_id=item.movie_id,
        watched=item.watched,
        added_at=item.added_at,
        movie=movie_to_out(movie),
    )
