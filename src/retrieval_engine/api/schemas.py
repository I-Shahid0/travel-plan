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


class ListingDetail(ListingResult):
    attributes: dict = {}
    postal_code: str | None = None
    is_open: bool = True


class FacetValue(BaseModel):
    value: str
    count: int


class BrowseFacets(BaseModel):
    cities: list[FacetValue]
    categories: list[FacetValue]


class BrowseResponse(BaseModel):
    total: int
    limit: int
    offset: int
    sort: str
    results: list[ListingResult]
    facets: BrowseFacets | None = None


class SimilarResponse(BaseModel):
    listing_id: str
    results: list[ListingResult]


class RecommendationRequest(BaseModel):
    """Seed ids ordered most-recent-first; recency controls centroid weighting."""

    seed_listing_ids: list[str]
    exclude_listing_ids: list[str] = []
    limit: int = 20


class RecommendationResponse(BaseModel):
    results: list[ListingResult]
    # result listing id -> the seed listing that pulled it into the feed
    anchors: dict[str, str] = {}
    seed_count: int
    strategy: str


class HealthResponse(BaseModel):
    status: str
    listings_count: int | None = None


class EvalSplitResponse(BaseModel):
    cutoff_date: str
    train_count: int
    test_count: int
    notes: str | None = None
