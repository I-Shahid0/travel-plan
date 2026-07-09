from pydantic import BaseModel


class ListingResult(BaseModel):
    id: str
    title: str
    description: str | None
    categories: list[str]
    city: str | None
    state: str | None
    price_level: int | None
    stars: float | None
    review_count: int
    primary_image_url: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class SearchResponse(BaseModel):
    query: str
    total: int
    results: list[ListingResult]
    mode: str = "hybrid"
    technique: str | None = None
    query_understanding: dict | None = None
    personalization: dict | None = None


class HealthResponse(BaseModel):
    status: str
    listings_count: int | None = None


class EvalSplitResponse(BaseModel):
    cutoff_date: str
    train_count: int
    test_count: int
    notes: str | None = None
