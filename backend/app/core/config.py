from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="AUTOSIGN_")

    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001"]

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
