"""Konfigurace nactena z promennych prostredi (.env)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "ano", "on"}


@dataclass(frozen=True)
class Settings:
    secret_key: str
    data_dir: Path
    admin_user: str
    admin_password: str
    admin_name: str
    secure_cookies: bool
    timezone: str
    max_upload_mb: int

    @property
    def db_path(self) -> Path:
        return self.data_dir / "nakupy.db"

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.db_path}"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"


def load_settings() -> Settings:
    data_dir = Path(os.getenv("NAKUPY_DATA_DIR", "./data")).expanduser().resolve()
    settings = Settings(
        secret_key=os.getenv("NAKUPY_SECRET_KEY", "dev-secret-zmen-me"),
        data_dir=data_dir,
        admin_user=os.getenv("NAKUPY_ADMIN_USER", "admin"),
        admin_password=os.getenv("NAKUPY_ADMIN_PASSWORD", "admin"),
        admin_name=os.getenv("NAKUPY_ADMIN_NAME", "Admin"),
        secure_cookies=_bool(os.getenv("NAKUPY_SECURE_COOKIES"), False),
        timezone=os.getenv("NAKUPY_TZ", "Europe/Prague"),
        max_upload_mb=int(os.getenv("NAKUPY_MAX_UPLOAD_MB", "40")),
    )
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    return settings
