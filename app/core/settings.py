from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Secrets are read only from the environment."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str
    telegram_bot_token: str | None = None
    image_provider_api_key: str | None = None
    image_model: str = "gpt-image-2.5-flare"
    generation_quality: str = "medium"
    generation_deadline_seconds: int = 120
    google_drive_service_account_json: str | None = None
    google_drive_folder_id: str | None = None
