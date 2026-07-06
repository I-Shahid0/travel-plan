from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://retrieval:retrieval@localhost:5432/retrieval"
    database_url_sync: str = "postgresql://retrieval:retrieval@localhost:5432/retrieval"
    data_dir: str = "data/archive"
    eval_split_cutoff: str = "2020-01-01"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_device: str = "cuda"
    embedding_dimension: int = 384
    embedding_batch_size: int = 256
    eval_sample_size: int = 10_000
    eval_k: int = 10
    beir_dataset: str = "scifact"
    results_dir: str = "results"
    rrf_k: int = 60
    hybrid_candidate_k: int = 100


settings = Settings()
