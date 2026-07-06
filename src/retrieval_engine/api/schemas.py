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


class SearchResponse(BaseModel):
    query: str
    total: int
    results: list[ListingResult]
    mode: str = "hybrid"


class HealthResponse(BaseModel):
    status: str
    listings_count: int | None = None


class EvalSplitResponse(BaseModel):
    cutoff_date: str
    train_count: int
    test_count: int
    notes: str | None = None
