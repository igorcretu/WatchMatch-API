"""Pydantic request/response schemas — decoupled from DB models."""
from pydantic import BaseModel, EmailStr
from typing import Optional, Literal


# ---------- Movie ----------
class MovieOut(BaseModel):
    id: str
    title: str
    year: int
    runtime: int
    rating: float
    genres: list[str]
    synopsis: str
    poster_path: str
    providers: list[str]
    hue: int
    variant: str
    mood: str
    content_type: str = "movie"
    language: str = "en"


# ---------- Auth ----------
class RegisterIn(BaseModel):
    name: str
    email: str
    password: str
    hue: int = 30


class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    name: str
    email: str
    hue: int
    partner_id: Optional[str]
    theme: str = "dark"


class InviteOut(BaseModel):
    token: str
    url: str


class PairByTokenIn(BaseModel):
    token: str


class DeleteAccountIn(BaseModel):
    password: str


# ---------- User ----------
class UserOut(BaseModel):
    id: str
    name: str
    email: str
    hue: int
    partner_id: Optional[str]
    theme: str = "dark"


class PairIn(BaseModel):
    partner_email: str


class UpdateThemeIn(BaseModel):
    theme: Literal["dark", "light"]


# ---------- Stats ----------
class GenreStat(BaseModel):
    genre: str
    count: int
    pct: int


class StatsOut(BaseModel):
    liked_count: int
    watched_count: int
    total_swipes: int
    match_count: int
    top_genres: list[GenreStat]
    agreement_rate: Optional[float]


# ---------- Filters ----------
class FilterPill(BaseModel):
    label: str
    state: Literal["nice", "must", "no"] = "nice"


class FiltersIn(BaseModel):
    genres: list[FilterPill]
    year_min: int = 2015
    year_max: int = 2025
    rating_min: float = 6.5
    runtime_max: int = 180
    providers: list[FilterPill]
    moods: list[FilterPill]


# ---------- Session ----------
class SessionCreate(BaseModel):
    partner_id: Optional[str] = None
    content_type: str = "both"
    solo: bool = False


class SessionOut(BaseModel):
    id: str
    user_id: str
    partner_id: Optional[str]
    status: str
    created_at: int
    content_type: str = "both"


# ---------- Swipe ----------
class SwipeIn(BaseModel):
    movie_id: str
    action: Literal["like", "pass", "super", "skip", "hide", "seen"]


class MatchResult(BaseModel):
    matched: bool
    movie: Optional[MovieOut] = None
    session_id: str


# ---------- Session Replay ----------
class SwipeReplayItem(BaseModel):
    movie_id: str
    movie_title: str
    action: str
    user_id: str
    timestamp: int


# ---------- Queue ----------
class QueueItemOut(BaseModel):
    id: str
    movie_id: str
    watched: bool
    added_at: int
    sort_order: int = 0
    movie: MovieOut
    rating: Optional[int] = None


class RateIn(BaseModel):
    rating: int  # 1–5


class ReorderIn(BaseModel):
    sort_order: int


# ---------- Presets ----------
class PresetIn(BaseModel):
    name: str
    filters: FiltersIn


class PresetOut(BaseModel):
    id: str
    name: str
    filters: FiltersIn


# ---------- Groups ----------
class GroupCreate(BaseModel):
    name: str


class GroupOut(BaseModel):
    id: str
    name: str
    creator_id: str
    invite_code: str
    member_count: int
    session_id: Optional[str] = None


class GroupMemberOut(BaseModel):
    user_id: str
    name: str
    hue: int
