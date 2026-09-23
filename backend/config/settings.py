"""Configuration management for news credibility verification backend."""

import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and defaults."""

    # Application settings
    APP_NAME: str = "AI News Credibility Verification Engine"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # CORS configuration
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Logging
    LOG_LEVEL: str = "INFO"

    # Input validation constraints
    MIN_INPUT_LENGTH: int = 20
    MAX_INPUT_LENGTH: int = 10000
    REQUEST_TIMEOUT_SECONDS: int = 60

    # API keys (optional during initial foundation)
    GOOGLE_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    NEWS_API_KEY: str | None = None
    BING_NEWS_API_KEY: str | None = None
    GOOGLE_CSE_API_KEY: str | None = None
    GOOGLE_CSE_CX: str | None = None
    TAVILY_API_KEY: str | None = None
    BRAVE_SEARCH_API_KEY: str | None = None
    GOOGLE_FACTCHECK_API_KEY: str | None = None

    # Retrieval provider selection
    NEWS_PROVIDER: str = "gdelt"
    WEB_SEARCH_PROVIDER: str = "tavily"
    WEB_SEARCH_FALLBACK: str = "brave"
    FACTCHECK_PROVIDER: str = "google"

    # Retrieval limits
    MAX_QUERIES_PER_CLAIM: int = 5
    MAX_RESULTS_PER_PROVIDER: int = 10
    MAX_TOTAL_EVIDENCE_PER_CLAIM: int = 20

    # Retrieval timing
    RETRIEVAL_TIMEOUT_SECONDS: int = 15
    RETRIEVAL_CACHE_TTL_SECONDS: int = 3600

    # GDELT-specific
    GDELT_TIMESPAN_DAYS: int = 7

    # Part 8: AI Evidence Reasoning Settings
    LLM_PROVIDER: str = "gemini"
    LLM_MODEL: str = "gemini-1.5-flash"
    LLM_TIMEOUT_SECONDS: int = 15
    LLM_MAX_OUTPUT_TOKENS: int = 1500
    LLM_TEMPERATURE: float = 0.1
    LLM_ENABLED: bool = False

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
