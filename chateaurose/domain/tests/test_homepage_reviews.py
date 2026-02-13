from datetime import datetime, timezone

from chateaurose.domain.services.homepage_reviews import HomepageReview, select_homepage_review


def test_select_homepage_review_returns_none_when_empty():
    assert select_homepage_review([]) is None


def test_select_homepage_review_prioritizes_featured():
    regular = HomepageReview(id=1, is_featured=False, created_at=datetime(2026, 1, 4, tzinfo=timezone.utc))
    featured = HomepageReview(id=2, is_featured=True, created_at=datetime(2026, 1, 2, tzinfo=timezone.utc))

    selected = select_homepage_review([regular, featured])

    assert selected == featured


def test_select_homepage_review_falls_back_to_latest():
    oldest = HomepageReview(id=1, is_featured=False, created_at=datetime(2026, 1, 2, tzinfo=timezone.utc))
    latest = HomepageReview(id=2, is_featured=False, created_at=datetime(2026, 1, 6, tzinfo=timezone.utc))

    selected = select_homepage_review([oldest, latest])

    assert selected == latest
