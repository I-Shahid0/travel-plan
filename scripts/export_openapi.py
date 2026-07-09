"""Export OpenAPI schemas from app imports (no running services needed).

Part of the Phase 9 type-safety pipeline:
Pydantic models -> OpenAPI JSON -> generated TypeScript (apps/web).
Run via `make generate-api`.
"""

import json
from pathlib import Path

from retrieval_engine.itinerary_service.main import app as itinerary_app
from retrieval_engine.main import app as query_app

OUT_DIR = Path(__file__).resolve().parents[1] / "apps" / "web" / "openapi"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, app in (("query", query_app), ("itinerary", itinerary_app)):
        path = OUT_DIR / f"{name}.openapi.json"
        path.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
        print(f"exported {path.relative_to(OUT_DIR.parents[1])}")


if __name__ == "__main__":
    main()
