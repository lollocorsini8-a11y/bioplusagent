from __future__ import annotations

from functools import lru_cache
from typing import Literal
from urllib.parse import unquote, urlsplit

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    auth_disabled: bool = False
    demo_mode: bool = True
    allow_self_registration: bool = True
    public_demo_enabled: bool = False
    cookie_secure: bool = False
    session_hours: int = 8
    consent_version: str = "biopulse-consent-v1"
    biometric_retention_days: int = 365
    clinical_retention_days: int = 730

    # Database: Postgres+pgvector in Docker; SQLite solo come fallback per i test.
    database_url: str = "postgresql+psycopg://biopulse:biopulse@localhost:5432/biopulse"
    redis_url: str = "redis://localhost:6379/0"

    # LLM (Groq + Llama 3.3). Senza chiave l'agente funziona in modalita' deterministica.
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    llm_timeout_s: int = 25

    # Alert (Twilio opzionale: senza credenziali l'invio e' simulato e registrato a DB)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from: str = ""
    clinician_phone: str = ""

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")

    @property
    def llm_configured(self) -> bool:
        return bool(self.groq_api_key.strip())

    def validate_security_settings(self) -> None:
        if self.auth_disabled and self.app_env != "test":
            raise RuntimeError("AUTH_DISABLED è consentito solo nell'ambiente di test.")
        if self.app_env == "production" and (self.demo_mode or not self.cookie_secure or self.auth_disabled):
            raise RuntimeError("Produzione richiede DEMO_MODE=false, COOKIE_SECURE=true e autenticazione attiva.")
        if self.app_env == "production":
            if self.allow_self_registration:
                raise RuntimeError("La registrazione pubblica degli atleti deve essere disattivata in produzione.")
            if not self.redis_url:
                raise RuntimeError("Produzione richiede Redis per sessione e protezione dei tentativi di accesso.")
            parsed_url = urlsplit(self.database_url)
            if not parsed_url.password or unquote(parsed_url.password) == "biopulse":
                raise RuntimeError("Produzione richiede una password database non predefinita.")
            origins = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
            if not origins or any(not origin.startswith("https://") for origin in origins):
                raise RuntimeError("In produzione CORS_ORIGINS deve contenere solo origini HTTPS esplicite.")
        if self.session_hours < 1 or self.biometric_retention_days < 1 or self.clinical_retention_days < 1:
            raise RuntimeError("Le durate di sessione e conservazione devono essere positive.")


@lru_cache
def get_settings() -> Settings:
    return Settings()
