"""
Centralized configuration. All secrets come from environment variables /
GCP Secret Manager at deploy time -- never hardcoded.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- GitHub ---
    github_token: str = ""
    github_webhook_secret: str = ""

    # --- Gemini / Vertex AI ---
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-pro"

    # --- GCP project / infra ---
    gcp_project_id: str = "code-kitchen-reviewer"
    gcp_region: str = "asia-south1"
    firestore_collection: str = "review_history"

    # --- Cloud Tasks (async queueing for burst PR volume) ---
    use_cloud_tasks: bool = False
    cloud_tasks_queue: str = "review-jobs"

    # --- App behaviour ---
    max_diff_chars: int = 60_000  # guard against huge diffs blowing the context window
    port: int = 8080


@lru_cache
def get_settings() -> Settings:
    return Settings()
