from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GEOLENS_", env_file=".env", extra="ignore")
    model_url: str = "http://127.0.0.1:8081"
    model_id: str = "Qwen/Qwen3.5-2B"
    model_revision: str = "15852e8c16360a2fea060d615a32b45270f8a8fc"
    database: str = "data/geolens.sqlite"
    osm_extract_database: str = "data/osm.sqlite"
    osm_extract_extra_databases: str = "data/osm-southern.sqlite"
    user_agent: str = "GeoLens/0.1 (educational IIT Bombay hackathon prototype)"
    overpass_urls: str = "https://overpass-api.de/api/interpreter,https://overpass.private.coffee/api/interpreter"
    public_origin: str = "http://localhost:5173"
    max_inflight: int = 5
    deadline_seconds: float = 75


settings = Settings()
