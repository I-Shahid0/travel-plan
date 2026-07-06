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
    reranker_url: str = "http://localhost:8001"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    reranker_onnx_model: str = "temsa/ms-marco-MiniLM-L-6-v2-onnx-cpu-qint8"
    reranker_device: str = "cuda"
    rerank_batch_size: int = 32
    rerank_timeout_sec: float = 30.0
    rerank_enabled: bool = True
    otel_enabled: bool = True
    otel_service_name: str = "query-service"
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    llm_provider: str = "mock"
    google_api_key: str = ""
    llm_model: str = "gemini-2.0-flash"
    query_understanding_enabled: bool = True
    query_technique: str = "none"
    multi_query_count: int = 3
    redis_url: str = "redis://localhost:6379/0"
    redis_timeout_sec: float = 1.0
    personalize_enabled: bool = True
    personalize_alpha: float = 0.3
    personalize_pool_k: int = 50
    personalize_pref_ttl_sec: int = 3600
    personalize_max_history: int = 50
    personalize_half_life_days: float = 365.0
    query_service_url: str = "http://localhost:8000"
    itinerary_top_k: int = 8
    itinerary_budget_ms: float = 6000.0
    itinerary_budget_usd: float = 0.002
    itinerary_search_timeout_sec: float = 15.0
    itinerary_port: int = 8002


settings = Settings()
