import json
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..db import get_session
from ..models.db_models import (
    Session as SessionModel, SwipeRecord, Match, QueueItem, SessionPreset, Movie, User
)
from ..models.schemas import (
    SessionCreate, SessionOut, SwipeIn, MatchResult, FiltersIn,
    PresetIn, PresetOut, MovieOut
)
from ..auth import get_current_user
from .movies import movie_to_out

router = APIRouter(prefix="/sessions", tags=["sessions"])

MATCH_EVERY_N = 4

DEFAULT_FILTERS: dict = {
    "genres": [
        {"label": "Drama", "state": "nice"}, {"label": "Comedy", "state": "nice"},
        {"label": "Thriller", "state": "nice"}, {"label": "Sci-Fi", "state": "nice"},
        {"label": "Romance", "state": "nice"}, {"label": "Action", "state": "nice"},
        {"label": "Mystery", "state": "nice"}, {"label": "Historical", "state": "nice"},
        {"label": "Adventure", "state": "nice"}, {"label": "Music", "state": "nice"},
        {"label": "Family", "state": "nice"},
    ],
    "year_min": 2015, "year_max": 2025, "rating_min": 6.5, "runtime_max": 180,
    "providers": [
        {"label": "Netflix", "state": "nice"}, {"label": "HBO Max", "state": "nice"},
        {"label": "Disney+", "state": "nice"}, {"label": "Mubi", "state": "nice"},
    ],
    "moods": [
        {"label": "feel-good", "state": "nice"}, {"label": "tense", "state": "nice"},
        {"label": "cerebral", "state": "nice"}, {"label": "dreamy", "state": "nice"},
        {"label": "cozy", "state": "nice"},
    ],
}


@router.post("", response_model=SessionOut, status_code=201)
def create_session(
    body: SessionCreate,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    session = SessionModel(
        user_id=current.id,
        partner_id=body.partner_id or current.partner_id,
        filters_json=json.dumps(DEFAULT_FILTERS),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return _session_out(session)


@router.get("/{session_id}", response_model=SessionOut)
def get_session(
    session_id: str,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    s = _get_or_404(session_id, db)
    _assert_participant(s, current.id)
    return _session_out(s)


@router.get("/{session_id}/filters", response_model=FiltersIn)
def get_filters(
    session_id: str,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    s = _get_or_404(session_id, db)
    _assert_participant(s, current.id)
    return FiltersIn(**json.loads(s.filters_json))


@router.patch("/{session_id}/filters", response_model=SessionOut)
def update_filters(
    session_id: str,
    filters: FiltersIn,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    s = _get_or_404(session_id, db)
    _assert_participant(s, current.id)
    s.filters_json = filters.model_dump_json()
    s.status = "active"
    db.add(s)
    db.commit()
    db.refresh(s)
    return _session_out(s)


@router.post("/{session_id}/swipe", response_model=MatchResult)
def record_swipe(
    session_id: str,
    swipe: SwipeIn,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    s = _get_or_404(session_id, db)
    _assert_participant(s, current.id)

    record = SwipeRecord(
        session_id=session_id,
        user_id=current.id,
        movie_id=swipe.movie_id,
        action=swipe.action,
    )
    db.add(record)

    # Add to queue on like/super
    if swipe.action in ("like", "super"):
        existing_q = db.exec(
            select(QueueItem).where(
                QueueItem.user_id == current.id,
                QueueItem.movie_id == swipe.movie_id,
            )
        ).first()
        if not existing_q:
            db.add(QueueItem(user_id=current.id, movie_id=swipe.movie_id))

        # Count likes in this session for this user
        like_count = db.exec(
            select(SwipeRecord).where(
                SwipeRecord.session_id == session_id,
                SwipeRecord.user_id == current.id,
                SwipeRecord.action.in_(["like", "super"]),
            )
        ).all()

        if (len(like_count) + 1) % MATCH_EVERY_N == 0:
            movie = db.get(Movie, swipe.movie_id)
            match = Match(session_id=session_id, movie_id=swipe.movie_id)
            db.add(match)
            s.status = "matched"
            db.add(s)
            db.commit()
            return MatchResult(
                matched=True,
                movie=movie_to_out(movie) if movie else None,
                session_id=session_id,
            )

    db.commit()
    return MatchResult(matched=False, session_id=session_id)


@router.get("/{session_id}/almost-matched", response_model=list[MovieOut])
def almost_matched(
    session_id: str,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    """Movies the current user liked but were not mutually matched."""
    s = _get_or_404(session_id, db)
    _assert_participant(s, current.id)

    matched_ids = {m.movie_id for m in db.exec(
        select(Match).where(Match.session_id == session_id)
    ).all()}

    liked_by_me = db.exec(
        select(SwipeRecord).where(
            SwipeRecord.session_id == session_id,
            SwipeRecord.user_id == current.id,
            SwipeRecord.action.in_(["like", "super"]),
        )
    ).all()

    almost = [
        movie_to_out(db.get(Movie, r.movie_id))
        for r in liked_by_me
        if r.movie_id not in matched_ids and db.get(Movie, r.movie_id)
    ]
    return almost


# ---------- Presets ----------

@router.get("/presets", response_model=list[PresetOut])
def list_presets(
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    presets = db.exec(select(SessionPreset).where(SessionPreset.user_id == current.id)).all()
    return [_preset_out(p) for p in presets]


@router.post("/presets", response_model=PresetOut, status_code=201)
def create_preset(
    body: PresetIn,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    preset = SessionPreset(
        user_id=current.id,
        name=body.name,
        filters_json=body.filters.model_dump_json(),
    )
    db.add(preset)
    db.commit()
    db.refresh(preset)
    return _preset_out(preset)


@router.delete("/presets/{preset_id}", status_code=204)
def delete_preset(
    preset_id: str,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    preset = db.get(SessionPreset, preset_id)
    if not preset or preset.user_id != current.id:
        raise HTTPException(status_code=404, detail="Preset not found")
    db.delete(preset)
    db.commit()


# ---------- helpers ----------

def _get_or_404(session_id: str, db: Session) -> SessionModel:
    s = db.get(SessionModel, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return s


def _assert_participant(s: SessionModel, user_id: str) -> None:
    if s.user_id != user_id and s.partner_id != user_id:
        raise HTTPException(status_code=403, detail="Not a participant")


def _session_out(s: SessionModel) -> SessionOut:
    return SessionOut(
        id=s.id,
        user_id=s.user_id,
        partner_id=s.partner_id,
        status=s.status,
        created_at=s.created_at,
    )


def _preset_out(p: SessionPreset) -> PresetOut:
    return PresetOut(
        id=p.id,
        name=p.name,
        filters=FiltersIn(**json.loads(p.filters_json)),
    )
