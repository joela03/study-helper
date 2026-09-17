from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import profiles, cards, transcripts, health, search, generate
from app.core.config import settings
from app.core.database import engine
from app.models import base


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables (use alembic migrations in production)
    async with engine.begin() as conn:
        await conn.run_sync(base.Base.metadata.create_all)
    yield
    # Shutdown
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
app.include_router(profiles.router, prefix="/api/profiles", tags=["profiles"])
app.include_router(transcripts.router, prefix="/api/transcripts", tags=["transcripts"])
app.include_router(cards.router, prefix="/api/cards", tags=["cards"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(generate.router, prefix="/api/generate", tags=["generate"])
