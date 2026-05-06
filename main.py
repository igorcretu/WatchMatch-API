"""WatchMatch API — FastAPI + SQLModel + SQLite.

Deployed on Raspberry Pi via Docker Compose.
Exposed publicly via Cloudflare Tunnel at matchapi.crig.dev.

Run locally:
    uvicorn main:app --reload --port 8050
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from app import db as _db
from app.data.fixtures import seed_movies
from app.routers import auth, movies, sessions, users, groups

ALLOWED_ORIGINS = [
    "http://localhost:4200",
    "http://localhost:3000",
    "https://watchmatch.crig.dev",
    "https://matchapi.crig.dev",
]

extra = os.getenv("EXTRA_ORIGINS", "")
if extra:
    ALLOWED_ORIGINS.extend(extra.split())


@asynccontextmanager
async def lifespan(_: FastAPI):
    _db.create_db_and_tables()
    _db.run_migrations()
    with Session(_db.engine) as db:
        seed_movies(db)
    yield


app = FastAPI(
    title="WatchMatch API",
    description="Couples movie-matching backend. Deployed on Raspberry Pi via Cloudflare Tunnel.",
    version="1.0.0",
    lifespan=lifespan,
    redirect_slashes=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https://.*\.netlify\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,     prefix="/api")
app.include_router(movies.router,   prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(users.router,    prefix="/api")
app.include_router(groups.router,   prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok", "service": "watchmatch-api"}
