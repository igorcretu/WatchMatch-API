import json
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..db import get_session
from ..models.db_models import (
    Session as SessionModel, SwipeRecord, Match, QueueItem, SessionPreset, Movie, User
)
from ..models.schemas import (
    SessionCreate, SessionOut, SwipeIn, MatchResult, FiltersIn,
    PresetIn, PresetOut, MovieOut, SwipeReplayItem,
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
    "year_min": 2000, "year_max": 2025, "rating_min": 6.0, "runtime_max": 200,
    "providers": [
        {"label": "Netflix", "state": "nice"}, {"label": "Max", "state": "nice"},
        {"label": "Disney+", "state": "nice"}, {"label": "Mubi", "state": "nice"},
        {"label": "Prime Video", "state": "nice"}, {"label": "Peacock", "state": "nice"},
        {"label": "Showtime", "state": "nice"}, {"label": "Paramount+", "state": "nice"},
    ],
    "moods": [
        {"label": "feel-good", "state": "nice"}, {"label": "tense", "state": "nice"},
        {"label": "cerebral", "state": "nice"}, {"label": "dreamy", "state": "nice"},
        {"label": "cozy", "state": "nice"}, {"label": "epic", "state": "nice"},
        {"label": "melancholy", "state": "nice"}, {"label": "mind-bending", "state": "nice"},
        {"label": "witty", "state": "nice"}, {"label": "fun", "state": "nice"},
    ],
}


# ---------- Presets (MUST come before /{session_id} routes to avoid route conflict) ----------

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


# ---------- Sessions ----------

@router.post("", response_model=SessionOut, status_code=201)
def create_session(
    body: SessionCreate,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    partner_id = None if body.solo else (body.partner_id if body.partner_id is not None else current.partner_id)
    session = SessionModel(
        user_id=current.id,
        partner_id=partner_id,
        filters_json=json.dumps(DEFAULT_FILTERS),
        content_type=body.content_type,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return _session_out(session)


@router.get("/{session_id}", response_model=SessionOut)
def get_session_by_id(
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

    if swipe.action in ("like", "super"):
        existing_q = db.exec(
            select(QueueItem).where(
                QueueItem.user_id == current.id,
                QueueItem.movie_id == swipe.movie_id,
            )
        ).first()
        if not existing_q:
            db.add(QueueItem(user_id=current.id, movie_id=swipe.movie_id))

        # Count existing likes for this user in this session (before this swipe commits)
        like_count = db.exec(
            select(SwipeRecord).where(
                SwipeRecord.session_id == session_id,
                SwipeRecord.user_id == current.id,
                SwipeRecord.action.in_(["like", "super"]),
            )
        ).all()

        # Avoid duplicate matches for same movie
        already_matched = db.exec(
            select(Match).where(
                Match.session_id == session_id,
                Match.movie_id == swipe.movie_id,
            )
        ).first()

        if not already_matched and len(like_count) % MATCH_EVERY_N == 0:
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
    """Movies the current user liked that were not mutually matched."""
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


@router.get("/{session_id}/replay", response_model=list[SwipeReplayItem])
def session_replay(
    session_id: str,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    """Full swipe history for a session — visible to participants only."""
    s = _get_or_404(session_id, db)
    _assert_participant(s, current.id)

    swipes = db.exec(
        select(SwipeRecord).where(SwipeRecord.session_id == session_id)
    ).all()

    result = []
    for sw in swipes:
        movie = db.get(Movie, sw.movie_id)
        result.append(SwipeReplayItem(
            movie_id=sw.movie_id,
            movie_title=movie.title if movie else sw.movie_id,
            action=sw.action,
            user_id=sw.user_id,
            timestamp=sw.timestamp,
        ))
    return result


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
        content_type=s.content_type,
    )


def _preset_out(p: SessionPreset) -> PresetOut:
    return PresetOut(
        id=p.id,
        name=p.name,
        filters=FiltersIn(**json.loads(p.filters_json)),
    )
