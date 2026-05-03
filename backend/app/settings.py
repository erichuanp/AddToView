from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    backend_port: int = Field(default=8787, alias="BACKEND_PORT")
    data_dir: Path = Field(default=Path("../data"), alias="DATA_DIR")
    frontend_origin: str = Field(default="http://localhost:5173", alias="FRONTEND_ORIGIN")
    serve_static: bool = Field(default=False, alias="ADDTOVIEW_SERVE_STATIC")
    static_dir: Path = Field(default=Path("../frontend/dist"), alias="ADDTOVIEW_STATIC_DIR")

    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_base_url: str = Field(default="", alias="LLM_BASE_URL")
    llm_model_id: str = Field(default="", alias="LLM_MODEL_ID")

    @property
    def resolved_data_dir(self) -> Path:
        d = self.data_dir
        if not d.is_absolute():
            d = (Path(__file__).resolve().parent.parent / d).resolve()
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def db_path(self) -> Path:
        return self.resolved_data_dir / "addtoview.db"

    @property
    def resolved_static_dir(self) -> Path:
        d = self.static_dir
        if not d.is_absolute():
            d = (Path(__file__).resolve().parent.parent / d).resolve()
        return d


settings = Settings()
