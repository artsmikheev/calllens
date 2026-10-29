from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    database_url: str = 'sqlite+aiosqlite:///./calllens_auth.db'
    database_url_test: str | None = None
    app_base_url: str = 'http://localhost:8000'
    email_mode: str = 'log'
    smtp_host: str = ''
    smtp_port: int = 587
    smtp_user: str = ''
    smtp_password: str = ''
    smtp_from: str = 'noreply@calllens.local'
    allowed_origins: str = 'http://localhost:8000'
    session_ttl_days: int = 30
    magic_link_ttl_minutes: int = 15
    invite_ttl_hours: int = 72
    auth_cookie_name: str = 'session'
    model_config = SettingsConfigDict(env_file='.env', extra='ignore', case_sensitive=False)

    @property
    def allowed_origin_list(self) -> list[str]:
        return [x.strip().rstrip('/') for x in self.allowed_origins.split(',') if x.strip()]

    @property
    def cookie_secure(self) -> bool:
        return self.app_base_url.lower().startswith('https://')


@lru_cache
def get_settings() -> AuthSettings:
    return AuthSettings()
