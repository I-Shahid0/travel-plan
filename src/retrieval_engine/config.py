from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://retrieval:retrieval@localhost:5432/retrieval"
    database_url_sync: str = "postgresql://retrieval:retrieval@localhost:5432/retrieval"
    data_dir: str = "data/archive"
    eval_split_cutoff: str = "2020-01-01"


settings = Settings()
