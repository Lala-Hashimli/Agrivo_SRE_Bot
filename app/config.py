from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    bot_data_mode: Literal["mock", "real"] = "mock"
    mock_scenario: str = "healthy-system"
    mock_data_dir: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent / "mock-data"
    )

    telegram_bot_token: str | None = None
    telegram_allowed_user_ids: Annotated[list[int], NoDecode] = Field(
        default_factory=list
    )
    telegram_allowed_chat_ids: Annotated[list[int], NoDecode] = Field(
        default_factory=list
    )
    telegram_incident_chat_id: int | None = None

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash"
    ai_analysis_enabled: bool = True
    ai_max_question_length: int = Field(default=1000, ge=50, le=4000)
    database_path: Path = Path("data/agrivo-sre-bot.db")

    agrivo_frontend_url: str = "http://localhost:8090"
    agrivo_backend_url: str = "http://localhost:5001"
    agrivo_backend_health_url: str = "http://localhost:5001/api/health"
    agrivo_backend_live_url: str = "http://localhost:5001/api/health/live"
    agrivo_backend_ready_url: str = "http://localhost:5001/api/health/ready"
    agrivo_backend_metrics_url: str = "http://localhost:5001/api/metrics"

    prometheus_url: str | None = None
    alertmanager_url: str | None = None
    grafana_url: str | None = None
    grafana_service_account_token: str | None = None
    grafana_render_enabled: bool = False
    grafana_dashboard_overview_url: str | None = None
    grafana_dashboard_backend_url: str | None = None
    grafana_dashboard_kubernetes_url: str | None = None
    grafana_dashboard_incidents_url: str | None = None

    kubernetes_in_cluster: bool = False
    kubernetes_context: str | None = None
    kubernetes_namespace_dev: str = "agrivo-dev"
    kubernetes_namespace_prod: str = "agrivo-prod"

    argocd_url: str | None = None
    argocd_token: str | None = None
    argocd_verify_tls: bool = True
    ghcr_registry: str = "ghcr.io"
    ghcr_frontend_image: str = "maryamjabrailova04/agrivo-frontend"
    ghcr_backend_image: str = "maryamjabrailova04/agrivo-backend"

    github_owner: str = "MaryamJabrailova04"
    github_repository: str = "Agrivo"
    github_token: str | None = None
    display_timezone: str = "Asia/Baku"
    http_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    http_max_retries: int = Field(default=3, ge=0, le=10)

    @field_validator(
        "telegram_allowed_user_ids", "telegram_allowed_chat_ids", mode="before"
    )
    @classmethod
    def parse_id_list(cls, value: object) -> object:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            try:
                return [int(item.strip()) for item in value.split(",") if item.strip()]
            except ValueError as error:
                raise ValueError(
                    "Telegram allowlists must contain comma-separated integer IDs"
                ) from error
        return value

    @field_validator(
        "telegram_bot_token",
        "telegram_incident_chat_id",
        "gemini_api_key",
        "github_token",
        "prometheus_url",
        "alertmanager_url",
        "grafana_url",
        "grafana_service_account_token",
        "grafana_dashboard_overview_url",
        "grafana_dashboard_backend_url",
        "grafana_dashboard_kubernetes_url",
        "grafana_dashboard_incidents_url",
        "kubernetes_context",
        "argocd_url",
        "argocd_token",
        mode="before",
    )
    @classmethod
    def empty_is_none(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("Invalid LOG_LEVEL")
        return normalized

    @model_validator(mode="after")
    def validate_production_allowlist(self) -> Settings:
        if (
            self.app_env == "production"
            and not self.telegram_allowed_user_ids
            and not self.telegram_allowed_chat_ids
        ):
            raise ValueError("Production requires a Telegram allowlist")
        return self

    @property
    def telegram_configured(self) -> bool:
        return bool(self.telegram_bot_token)

    @property
    def ai_configured(self) -> bool:
        return bool(self.ai_analysis_enabled and self.gemini_api_key)

    @property
    def active_namespace(self) -> str:
        return (
            self.kubernetes_namespace_prod
            if self.app_env == "production"
            else self.kubernetes_namespace_dev
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
