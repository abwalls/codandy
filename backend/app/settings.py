from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    SettingsConfigDict,
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CODANDY_", env_file=".env", extra="ignore")

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):
        # Existing installations can migrate without losing report/auth settings.
        return (init_settings, env_settings,
                EnvSettingsSource(settings_cls, env_prefix="CODE_ATLAS_"), dotenv_settings,
                DotEnvSettingsSource(settings_cls, env_file=dotenv_settings.env_file, env_prefix="CODE_ATLAS_"),
                file_secret_settings)

    environment: str = "development"
    allowed_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    workspace_root: str = ".workspaces"
    # Opt-in local, single-process persistence for completed reports and captured source.
    report_root: str | None = None
    investigation_root: str | None = ".investigations"
    sentry_token: SecretStr = SecretStr("")
    sentry_host: Literal["sentry.io", "us.sentry.io", "de.sentry.io"] = "sentry.io"
    sentry_organization: str = ""
    codex_enabled: bool = False
    codex_executable: str = ""
    codex_home: str = ".codex-codandy"
    max_repository_mb: int = Field(default=250, ge=1, le=1000)
    # Compressed ZIP upload size. Extracted content is still bounded by max_repository_mb.
    max_upload_mb: int = Field(default=100, ge=1, le=1000)
    max_file_count: int = Field(default=25000, ge=1, le=100000)
    max_path_depth: int = Field(default=30, ge=1, le=100)
    clone_timeout_seconds: int = Field(default=120, ge=1, le=600)
    analysis_timeout_seconds: int = Field(default=120, ge=1, le=600)
    max_source_bytes: int = Field(default=1_000_000, ge=1024, le=10_000_000)
    max_nodes: int = Field(default=50000, ge=10, le=200000)
    max_jobs: int = Field(default=10, ge=1, le=100)
    # Source text retained per report so the viewer can show evidence after the
    # workspace is destroyed. Held in memory and evicted with the report.
    max_viewer_file_bytes: int = Field(default=131_072, ge=1024, le=1_000_000)
    max_viewer_total_bytes: int = Field(default=4_194_304, ge=4096, le=67_108_864)


settings = Settings()
