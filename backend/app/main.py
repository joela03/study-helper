from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import profiles, cards, transcripts, health, search, generate, concepts, materials, auth
from app.core.config import settings
from app.core.database import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    allow_origins=settings.CORS_ORIGINS,
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
