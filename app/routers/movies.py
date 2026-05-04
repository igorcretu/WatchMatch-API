from fastapi import APIRouter, Depends, HTTPException
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
    )


router = APIRouter(prefix="/movies", tags=["movies"])


@router.get("/", response_model=list[MovieOut])
def list_movies(
    genre: str | None = None,
    provider: str | None = None,
    year_min: int = 2000,
    year_max: int = 2030,
    rating_min: float = 0.0,
    runtime_max: int = 999,
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

    if genre:
        results = [m for m in results if genre in m.genres.split(",")]
    if provider:
        results = [m for m in results if provider in m.providers.split(",")]
    results = [m for m in results if year_min <= m.year <= year_max]
    results = [m for m in results if m.rating >= rating_min]
    results = [m for m in results if m.runtime <= runtime_max]

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
