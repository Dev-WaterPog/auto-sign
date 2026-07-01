from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="AUTOSIGN_")

    # Plain comma-separated string rather than list[str]: pydantic-settings
    # requires JSON array syntax (e.g. '["a","b"]') for list-typed env vars
    # and raises a SettingsError otherwise — too easy to get wrong when
    # typing into a hosting dashboard's plain-text env var field.
    cors_origins_csv: str = Field(
        default="http://localhost:3000,http://localhost:3001",
        validation_alias="AUTOSIGN_CORS_ORIGINS",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_csv.split(",") if origin.strip()]

    # Shared access token required on every API request (via the
    # X-Access-Token header) once set. Leave empty for local development
    # (auth is skipped entirely) — always set this before deploying publicly.
    access_token: str = ""

    storage_dir: Path = Path(__file__).resolve().parents[1] / "storage"
    signatures_dir: Path = storage_dir / "signatures"
    templates_dir: Path = storage_dir / "templates"
    output_dir: Path = storage_dir / "output"

    # Default anchor pattern used to locate where the signature/date should
    # be stamped when the caller doesn't supply one. Matches common Thai/English
    # signing labels, e.g. "ลงชื่อ", "ผู้ตรวจสอบ", "Signature:", "Date:".
    default_signature_anchor: str = r"(ลงช(ื่|ือ)อ|ผู้เซ็น|Signature)\s*[:：]?"
    default_date_anchor: str = r"(วันที่|Date)\s*[:：]?"

    def ensure_dirs(self) -> None:
        for d in (self.signatures_dir, self.templates_dir, self.output_dir):
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
