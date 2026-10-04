from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://studyhelper:studyhelper@localhost:5432/studyhelper"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # LLM APIs
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GROQ_API_KEY: str = ""

    # Models for different tasks
    FLASHCARD_MODEL: str = "gpt-4o-mini"  # Cheap model for high-frequency generation
    LESSON_MODEL: str = "gpt-4o"  # Stronger model for quality-sensitive lessons
    # Groq's free tier caps output at 1000 tokens/minute and rejects any
    # single request expecting more, so the ceiling sits just under it.
    # Raise this if you move to a paid tier or another provider.
    LLM_MAX_OUTPUT_TOKENS: int = 900
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"  # Local sentence-transformers model

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # File uploads
    UPLOAD_DIR: str = "/app/uploads"
    MAX_UPLOAD_SIZE_MB: int = 100

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
