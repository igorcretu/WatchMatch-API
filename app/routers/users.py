import csv
import io
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select, or_

from ..db import get_session
from ..models.db_models import User, QueueItem, Match, Movie, SwipeRecord, Session as SessionModel
from ..models.schemas import UserOut, QueueItemOut, RateIn, MovieOut, StatsOut, GenreStat, ReorderIn
from ..auth import get_current_user
from .movies import movie_to_out

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me/queue", response_model=list[QueueItemOut])
def get_queue(
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    items = db.exec(
        select(QueueItem)
        .where(QueueItem.user_id == current.id, QueueItem.watched == False)
        .order_by(QueueItem.sort_order, QueueItem.added_at)
    ).all()
    return [_queue_item_out(item, db, current.id) for item in items]


@router.get("/me/history", response_model=list[QueueItemOut])
def get_history(
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    items = db.exec(
        select(QueueItem)
        .where(QueueItem.user_id == current.id, QueueItem.watched == True)
        .order_by(QueueItem.added_at.desc())
    ).all()
    return [_queue_item_out(item, db, current.id) for item in items]


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
    return _queue_item_out(item, db, current.id)


@router.patch("/me/queue/{movie_id}/reorder", response_model=QueueItemOut)
def reorder_queue_item(
    movie_id: str,
    body: ReorderIn,
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
    item.sort_order = body.sort_order
    db.add(item)
    db.commit()
    db.refresh(item)
    return _queue_item_out(item, db, current.id)


@router.patch("/me/history/{movie_id}/rate", response_model=QueueItemOut)
def rate_watched(
    movie_id: str,
    body: RateIn,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    if not (1 <= body.rating <= 5):
        raise HTTPException(status_code=422, detail="Rating must be 1–5")

    # Find a match for this movie in any session the current user participated in
    match = db.exec(
        select(Match)
        .join(SessionModel, Match.session_id == SessionModel.id)
        .where(
            Match.movie_id == movie_id,
            or_(SessionModel.user_id == current.id, SessionModel.partner_id == current.id),
        )
    ).first()

    if match:
        s = db.get(SessionModel, match.session_id)
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
    return _queue_item_out(item, db, current.id)


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


@router.get("/me/stats", response_model=StatsOut)
def get_stats(
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    all_queue = db.exec(select(QueueItem).where(QueueItem.user_id == current.id)).all()
    liked_count = len(all_queue)
    watched_count = sum(1 for q in all_queue if q.watched)

    total_swipes = db.exec(
        select(SwipeRecord).where(SwipeRecord.user_id == current.id)
    ).all()

    # Matches in sessions this user participated in
    sessions_i_was_in = db.exec(
        select(SessionModel).where(
            or_(SessionModel.user_id == current.id, SessionModel.partner_id == current.id)
        )
    ).all()
    session_ids = {s.id for s in sessions_i_was_in}
    match_count = 0
    if session_ids:
        all_matches = db.exec(
            select(Match).where(Match.session_id.in_(session_ids))
        ).all()
        match_count = len(all_matches)

    # Genre aggregation from liked movies
    genre_counts: dict[str, int] = {}
    for item in all_queue:
        movie = db.get(Movie, item.movie_id)
        if movie:
            for g in (movie.genres or "").split(","):
                g = g.strip()
                if g:
                    genre_counts[g] = genre_counts.get(g, 0) + 1

    total_genre_likes = sum(genre_counts.values()) or 1
    top_genres = sorted(genre_counts.items(), key=lambda x: -x[1])[:5]
    genre_stats = [
        GenreStat(genre=g, count=c, pct=round(c / total_genre_likes * 100))
        for g, c in top_genres
    ]

    # Agreement rate: percentage of liked movies that became matches
    agreement_rate = round(match_count / liked_count * 100, 1) if liked_count > 0 else None

    return StatsOut(
        liked_count=liked_count,
        watched_count=watched_count,
        total_swipes=len(total_swipes),
        match_count=match_count,
        top_genres=genre_stats,
        agreement_rate=agreement_rate,
    )


@router.get("/me/export")
def export_queue(
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    """Download the full watchlist as CSV."""
    items = db.exec(select(QueueItem).where(QueueItem.user_id == current.id)).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["title", "year", "runtime", "rating", "genres", "providers", "watched"])
    for item in items:
        movie = db.get(Movie, item.movie_id)
        if movie:
            writer.writerow([
                movie.title, movie.year, movie.runtime, movie.rating,
                movie.genres, movie.providers, item.watched,
            ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=watchlist.csv"},
    )


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
        theme=user.theme,
    )


def _queue_item_out(item: QueueItem, db: Session, user_id: str) -> QueueItemOut:
    movie = db.get(Movie, item.movie_id)
    if not movie:
        raise HTTPException(status_code=500, detail=f"Movie {item.movie_id} missing from DB")

    # Look up post-watch rating from Match record
    rating = None
    match = db.exec(
        select(Match)
        .join(SessionModel, Match.session_id == SessionModel.id)
        .where(
            Match.movie_id == item.movie_id,
            or_(SessionModel.user_id == user_id, SessionModel.partner_id == user_id),
        )
    ).first()
    if match:
        s = db.get(SessionModel, match.session_id)
        if s:
            rating = match.user1_rating if s.user_id == user_id else match.user2_rating

    return QueueItemOut(
        id=item.id,
        movie_id=item.movie_id,
        watched=item.watched,
        added_at=item.added_at,
        sort_order=item.sort_order,
        movie=movie_to_out(movie),
        rating=rating,
    )
