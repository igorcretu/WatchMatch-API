"""Pydantic request/response schemas — decoupled from DB models."""
from __future__ import annotations
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


# ---------- User ----------
class UserOut(BaseModel):
    id: str
    name: str
    email: str
    hue: int
    partner_id: Optional[str]


class PairIn(BaseModel):
    partner_email: str


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


class SessionOut(BaseModel):
    id: str
    user_id: str
    partner_id: Optional[str]
    status: str
    created_at: int


# ---------- Swipe ----------
class SwipeIn(BaseModel):
    movie_id: str
    action: Literal["like", "pass", "super", "skip", "hide", "seen"]


class MatchResult(BaseModel):
    matched: bool
    movie: Optional[MovieOut] = None
    session_id: str


# ---------- Queue ----------
class QueueItemOut(BaseModel):
    id: str
    movie_id: str
    watched: bool
    added_at: int
    movie: MovieOut


class RateIn(BaseModel):
    rating: int  # 1–5


# ---------- Presets ----------
class PresetIn(BaseModel):
    name: str
    filters: FiltersIn


class PresetOut(BaseModel):
    id: str
    name: str
    filters: FiltersIn
