"""Application configuration (env-driven)."""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Auth ---
    secret_key: str = "change-me-in-production-please-32chars-min"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 8 * 60

    # --- Default admin (created on first run by seed.py) ---
    admin_username: str = "admin"
    admin_password: str = "admin123"

    # --- Database ---
    database_url: str = f"sqlite:///{(BASE_DIR / 'database' / 'network.db').as_posix()}"

    # --- Networking / deployment ---
    ip_pool_base: str = "10.10.0.0/16"      # pool used by the smart auto-configurator
    vlan_id_start: int = 10                  # first VLAN id allocated
    ssh_timeout: int = 20
    deploy_dry_run: bool = False             # if True, generate config but never touch devices

    # --- CORS ---
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
