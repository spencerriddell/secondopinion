from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Second Opinion Clinical Decision Support"
    fastapi_env: str = "development"
    log_level: str = "INFO"

    llm_backend: str = Field(default="ollama", alias="LLM_BACKEND")
    llm_model: str = Field(default="mistral", alias="LLM_MODEL")
    llm_endpoint: str | None = Field(default=None, alias="LLM_ENDPOINT")
    ncbi_email: str = Field(alias="NCBI_EMAIL")
    pubmed_api_key: str | None = Field(default=None, alias="PUBMED_API_KEY")
    pmc_email: str | None = Field(default=None, alias="PMC_EMAIL")
    pmc_batch_size: int = Field(default=5, alias="PMC_BATCH_SIZE")


@lru_cache
def get_settings() -> Settings:
    return Settings()
