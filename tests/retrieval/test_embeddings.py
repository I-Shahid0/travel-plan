from retrieval_engine.retrieval.embeddings import listing_document


class FakeListing:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def test_listing_document_concatenates_fields():
    listing = FakeListing(
        title="Joe's Pizza",
        categories=["Pizza", "Italian"],
        description="Best slice in town",
        review_text="Great crust",
    )
    doc = listing_document(listing)
    assert "Joe's Pizza" in doc
    assert "Pizza" in doc
    assert "Best slice" in doc
    assert "Great crust" in doc


def test_listing_document_truncates_review():
    listing = FakeListing(title="Shop", categories=[], description=None, review_text="x" * 5000)
    doc = listing_document(listing)
    assert len(doc) <= len("Shop") + 1 + 2000
