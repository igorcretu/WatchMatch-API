"""SQLModel table models — these map directly to SQLite tables."""
import uuid
from typing import Optional
from sqlmodel import Field, SQLModel, Relationship


def new_id() -> str:
    return str(uuid.uuid4())


class User(SQLModel, table=True):
    __tablename__ = "users"
    id: str = Field(default_factory=new_id, primary_key=True)
    name: str
    email: str = Field(unique=True, index=True)
    hashed_password: str
    hue: int = 30
    partner_id: Optional[str] = Field(default=None, foreign_key="users.id")
    invite_token: Optional[str] = Field(default=None)
    theme: str = Field(default="dark")

    swipes: list["SwipeRecord"] = Relationship(back_populates="user")
    presets: list["SessionPreset"] = Relationship(back_populates="user")


class Movie(SQLModel, table=True):
    __tablename__ = "movies"
    id: str = Field(primary_key=True)
    title: str
    year: int
    runtime: int
    rating: float
    genres: str           # comma-separated
    synopsis: str
    poster_path: str = ""
    providers: str        # comma-separated
    hue: int = 30
    variant: str = "gradient"
    mood: str = ""
    content_type: str = Field(default="movie")
    language: str = Field(default="en")


class Session(SQLModel, table=True):
    __tablename__ = "sessions"
    id: str = Field(default_factory=new_id, primary_key=True)
    user_id: str = Field(foreign_key="users.id")
    partner_id: Optional[str] = Field(default=None, foreign_key="users.id")
    status: str = "waiting"   # waiting | active | matched | no-match
    filters_json: str = "{}"  # Filters stored as JSON blob
    content_type: str = Field(default="both")  # movie | series | both
    created_at: int = Field(default_factory=lambda: __import__("time").time_ns() // 1_000_000)

    swipes: list["SwipeRecord"] = Relationship(back_populates="session")
    matches: list["Match"] = Relationship(back_populates="session")


class SwipeRecord(SQLModel, table=True):
    __tablename__ = "swipe_records"
    id: str = Field(default_factory=new_id, primary_key=True)
    session_id: str = Field(foreign_key="sessions.id", index=True)
    user_id: str = Field(foreign_key="users.id", index=True)
    movie_id: str = Field(foreign_key="movies.id")
    action: str  # like | pass | super | skip | hide | seen
    timestamp: int = Field(default_factory=lambda: __import__("time").time_ns() // 1_000_000)

    session: Optional[Session] = Relationship(back_populates="swipes")
    user: Optional[User] = Relationship(back_populates="swipes")


class Match(SQLModel, table=True):
    __tablename__ = "matches"
    id: str = Field(default_factory=new_id, primary_key=True)
    session_id: str = Field(foreign_key="sessions.id", index=True)
    movie_id: str = Field(foreign_key="movies.id")
    user1_rating: Optional[int] = None   # 1-5 post-watch
    user2_rating: Optional[int] = None

    session: Optional[Session] = Relationship(back_populates="matches")


class QueueItem(SQLModel, table=True):
    __tablename__ = "queue_items"
    id: str = Field(default_factory=new_id, primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True)
    movie_id: str = Field(foreign_key="movies.id")
    watched: bool = False
    added_at: int = Field(default_factory=lambda: __import__("time").time_ns() // 1_000_000)
    sort_order: int = Field(default=0)


class SessionPreset(SQLModel, table=True):
    __tablename__ = "session_presets"
    id: str = Field(default_factory=new_id, primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True)
    name: str
    filters_json: str = "{}"

    user: Optional[User] = Relationship(back_populates="presets")


class Group(SQLModel, table=True):
    __tablename__ = "groups"
    id: str = Field(default_factory=new_id, primary_key=True)
    name: str
    creator_id: str = Field(foreign_key="users.id")
    invite_code: str = Field(default_factory=lambda: str(uuid.uuid4())[:8].upper())
    session_id: Optional[str] = Field(default=None, foreign_key="sessions.id")

    members: list["GroupMember"] = Relationship(back_populates="group")


class GroupMember(SQLModel, table=True):
    __tablename__ = "group_members"
    id: str = Field(default_factory=new_id, primary_key=True)
    group_id: str = Field(foreign_key="groups.id", index=True)
    user_id: str = Field(foreign_key="users.id")

    group: Optional[Group] = Relationship(back_populates="members")
