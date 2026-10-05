from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import profiles, cards, transcripts, health, search, generate, concepts, materials, auth
from app.core.config import settings
from app.core.database import engine


INSECURE_SECRET = "dev-only-insecure-change-me"


def _check_production_config() -> None:
    """
    Refuse to start in production with settings that are only safe locally.

    A default signing key means anyone can mint a token for any account, and
    it fails silently — the app works perfectly until someone notices.
    """
    if settings.ENVIRONMENT != "production":
        return

    problems = []
    if settings.SECRET_KEY == INSECURE_SECRET:
        problems.append("SECRET_KEY is still the development default")
    if any("localhost" in origin for origin in settings.cors_origins):
        problems.append(f"CORS_ORIGINS still points at localhost: {settings.cors_origins}")
    if "studyhelper:studyhelper@" in settings.DATABASE_URL:
        problems.append("DATABASE_URL still uses the default password")

    if problems:
        raise RuntimeError(
            "Refusing to start in production:\n  - " + "\n  - ".join(problems)
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _check_production_config()

    # Schema is owned by Alembic — run `alembic upgrade head` before start.
    # create_all only ever created missing tables and never altered existing
    # ones, so column changes silently didn't apply.

    # Start scheduler for daily reminders
    from app.tasks.scheduler import start_scheduler, stop_scheduler
    start_scheduler()

    yield

    # Shutdown
    stop_scheduler()
    await engine.dispose()


app = FastAPI(
    title="Study Helper API",
    description="AI-powered study tool with spaced repetition",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(health.router, tags=["health"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(profiles.router, prefix="/api/profiles", tags=["profiles"])
app.include_router(transcripts.router, prefix="/api/transcripts", tags=["transcripts"])
app.include_router(cards.router, prefix="/api/cards", tags=["cards"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(generate.router, prefix="/api/generate", tags=["generate"])
app.include_router(concepts.router, prefix="/api/concepts", tags=["concepts"])
app.include_router(materials.router, prefix="/api/materials", tags=["materials"])
