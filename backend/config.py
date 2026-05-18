from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    groq_api_key: str
    database_url: str = "sqlite:///./multilevel.db"
    audio_upload_dir: str = "./audio_uploads"
    debug: bool = False

    groq_model: str = "llama-3.3-70b-versatile"
    # Whisper variant used for server-side transcription. `whisper-large-v3`
    # is the most accurate Groq offers; swap to `whisper-large-v3-turbo`
    # if you want roughly 2x faster transcription with a small accuracy
    # trade-off.
    groq_whisper_model: str = "whisper-large-v3"

    @property
    def audio_dir(self) -> Path:
        p = Path(self.audio_upload_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        try:
            _settings = Settings()
        except Exception as e:
            raise RuntimeError(
                "Failed to load settings. Ensure .env exists with GROQ_API_KEY. "
                "Get a free key at https://console.groq.com/keys. "
                f"Underlying error: {e}"
            ) from e
    return _settings
