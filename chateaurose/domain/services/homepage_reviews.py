from dataclasses import dataclass
from datetime import datetime
from typing import Iterable


@dataclass(frozen=True)
class HomepageReview:
    id: int
    is_featured: bool
    created_at: datetime


def select_homepage_review(reviews: Iterable[HomepageReview]) -> HomepageReview | None:
    sorted_reviews = sorted(
        reviews,
        key=lambda review: (
            0 if review.is_featured else 1,
            -review.created_at.timestamp(),
            -review.id,
        ),
    )
    if not sorted_reviews:
        return None
    return sorted_reviews[0]
