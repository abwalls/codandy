from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CODE_ATLAS_", env_file=".env")

    environment: str = "development"
    allowed_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    workspace_root: str = ".workspaces"
    # Opt-in local, single-process persistence for completed reports and captured source.
    report_root: str | None = None
    codex_enabled: bool = False
    codex_executable: str = ""
    codex_home: str = ".codex-atlas"
    max_repository_mb: int = Field(default=250, ge=1, le=1000)
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
