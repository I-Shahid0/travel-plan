from __future__ import annotations

import math
from dataclasses import dataclass

from sqlalchemy import and_, func, or_, text
from sqlalchemy.sql import Select

from retrieval_engine.db.models import Listing


@dataclass(frozen=True)
class SearchFilters:
    """Structured constraints applied before hybrid candidate retrieval."""

    price_max: int | None = None
    category: str | None = None
    city: str | None = None
    lat: float | None = None
    lon: float | None = None
    radius_km: float | None = None

    def has_geo(self) -> bool:
        return (
            self.lat is not None
            and self.lon is not None
            and self.radius_km is not None
            and self.radius_km > 0
        )

    def is_empty(self) -> bool:
        return not any(
            [
                self.price_max is not None,
                self.category,
                self.city,
                self.has_geo(),
            ]
        )

    def apply(self, stmt: Select) -> Select:
        conditions = self.conditions()
        if not conditions:
            return stmt
        return stmt.where(and_(*conditions))

    def conditions(self) -> list:
        clauses: list = []

        if self.price_max is not None:
            clauses.append(
                and_(Listing.price_level.isnot(None), Listing.price_level <= self.price_max)
            )

        if self.category:
            pattern = f"%{self.category}%"
            clauses.append(
                or_(
                    func.array_to_string(Listing.categories, " ").ilike(pattern),
                    Listing.categories.contains([self.category]),
                )
            )

        if self.city:
            clauses.append(Listing.city.ilike(f"%{self.city}%"))

        if self.has_geo():
            lat_rad = math.radians(self.lat)  # type: ignore[arg-type]
            lon_rad = math.radians(self.lon)  # type: ignore[arg-type]
            radius = self.radius_km
            clauses.append(
                and_(
                    Listing.latitude.isnot(None),
                    Listing.longitude.isnot(None),
                    text(
                        """
                        6371 * acos(
                            LEAST(1.0, GREATEST(-1.0,
                                cos(:lat_rad) * cos(radians(latitude)) *
                                cos(radians(longitude) - :lon_rad) +
                                sin(:lat_rad) * sin(radians(latitude))
                            ))
                        ) <= :radius_km
                        """
                    ).bindparams(lat_rad=lat_rad, lon_rad=lon_rad, radius_km=radius),
                )
            )

        return clauses
