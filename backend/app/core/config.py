from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # "development" or "production"; production refuses insecure defaults
    ENVIRONMENT: str = "development"

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

    # Comma-separated, e.g.
    # CORS_ORIGINS=https://study.example.com,https://www.study.example.com
    #
    # Kept as a plain string: pydantic-settings tries to JSON-parse any
    # complex type straight from the environment, so a list field rejects a
    # bare URL before any validator can run. Read cors_origins instead.
    CORS_ORIGINS: str = "http://localhost:3000"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    # Auth. SECRET_KEY must be set from the environment in any real
    # deployment — the default exists only so local dev runs out of the box.
    SECRET_KEY: str = "dev-only-insecure-change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 14
    # Closed sign-ups by default: an open registration endpoint on a
    # public URL is an invitation to strangers to use your LLM quota.
    REQUIRE_INVITE: bool = True

    # Whisper is not installed by default — see requirements.txt
    ENABLE_AUDIO_TRANSCRIPTION: bool = False

    # File uploads
    UPLOAD_DIR: str = "/app/uploads"
    MAX_UPLOAD_SIZE_MB: int = 100

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
