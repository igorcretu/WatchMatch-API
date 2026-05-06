from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from ..db import get_session
from ..models.db_models import Movie, SwipeRecord
from ..models.schemas import MovieOut
from ..auth import get_current_user, User


def movie_to_out(m: Movie) -> MovieOut:
    return MovieOut(
        id=m.id,
        title=m.title,
        year=m.year,
        runtime=m.runtime,
        rating=m.rating,
        genres=m.genres.split(",") if m.genres else [],
        synopsis=m.synopsis,
        poster_path=m.poster_path,
        providers=m.providers.split(",") if m.providers else [],
        hue=m.hue,
        variant=m.variant,
        mood=m.mood,
        content_type=m.content_type,
        language=m.language,
    )


router = APIRouter(prefix="/movies", tags=["movies"])


@router.get("", response_model=list[MovieOut])
def list_movies(
    q: str | None = None,
    year_min: int = 1990,
    year_max: int = 2030,
    rating_min: float = 0.0,
    runtime_max: int = 999,
    content_type: str | None = None,
    language: str | None = None,
    genres_must: list[str] = Query(default=[]),
    genres_no: list[str] = Query(default=[]),
    providers_must: list[str] = Query(default=[]),
    providers_no: list[str] = Query(default=[]),
    moods_must: list[str] = Query(default=[]),
    moods_no: list[str] = Query(default=[]),
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    # Exclude hidden/already-seen movies for this user
    hidden_ids = set(
        db.exec(
            select(SwipeRecord.movie_id).where(
                SwipeRecord.user_id == current.id,
                SwipeRecord.action.in_(["hide", "seen"]),
            )
        ).all()
    )

    movies = db.exec(select(Movie)).all()
    results = [m for m in movies if m.id not in hidden_ids]

    # Text search by title
    if q:
        ql = q.lower()
        results = [m for m in results if ql in m.title.lower()]

    # Numeric range filters
    results = [m for m in results if year_min <= m.year <= year_max]
    results = [m for m in results if m.rating >= rating_min]
    results = [m for m in results if m.runtime <= runtime_max]

    # Content type filter (movie | series | both)
    if content_type and content_type != "both":
        results = [m for m in results if m.content_type == content_type]

    # Language filter
    if language:
        results = [m for m in results if m.language == language]

    # Genre filters
    if genres_must:
        results = [m for m in results if any(g in m.genres.split(",") for g in genres_must)]
    if genres_no:
        results = [m for m in results if not any(g in m.genres.split(",") for g in genres_no)]

    # Provider filters
    if providers_must:
        results = [m for m in results if any(p in m.providers.split(",") for p in providers_must)]
    if providers_no:
        results = [m for m in results if not any(p in m.providers.split(",") for p in providers_no)]

    # Mood filters
    if moods_must:
        results = [m for m in results if m.mood in moods_must]
    if moods_no:
        results = [m for m in results if m.mood not in moods_no]

    return [movie_to_out(m) for m in results]


@router.get("/{movie_id}", response_model=MovieOut)
def get_movie(
    movie_id: str,
    db: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    movie = db.get(Movie, movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    return movie_to_out(movie)
