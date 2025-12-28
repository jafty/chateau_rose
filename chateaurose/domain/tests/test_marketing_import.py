import json

import pytest

from chateaurose.domain.exceptions import ValidationError
from chateaurose.domain.use_cases import import_marketing_content
from chateaurose.domain.tests.stubs.marketing_repository import (
    InMemoryMarketingContentRepository,
)


def _sample_payload():
    return {
        "services": [
            {
                "slug": "tresses",
                "name": "Tresses",
                "intro": "Base intro",
                "highlights": ["Rapide"],
                "main_image": "service.jpg",
                "main_image_url": "https://static.example.com/service.jpg",
                "meta_description": "Meta",
                "gallery": ["g1.jpg", "g2.jpg"],
            }
        ]
    }


def test_valid_payload_builds_bundle_and_calls_repository():
    repository = InMemoryMarketingContentRepository()
    payload = _sample_payload()

    result = import_marketing_content.execute(payload=payload, repository=repository)

    assert repository.calls == 1
    bundle = repository.received_bundle
    assert len(bundle.services) == 1
    assert bundle.services[0].slug == "tresses"
    assert bundle.services[0].main_image_url == "https://static.example.com/service.jpg"
    assert result.services_count == 1


def test_duplicate_service_slug_rejected():
    payload = _sample_payload()
    payload["services"].append({"slug": "tresses", "name": "Tresses bis"})
    repository = InMemoryMarketingContentRepository()

    with pytest.raises(ValidationError):
        import_marketing_content.execute(payload=payload, repository=repository)

    assert repository.calls == 0


def test_invalid_highlights_type_rejected_before_persisting():
    payload = _sample_payload()
    payload["services"][0]["highlights"] = "Rapide"
    repository = InMemoryMarketingContentRepository()

    with pytest.raises(ValidationError):
        import_marketing_content.execute(payload=payload, repository=repository)

    assert repository.calls == 0
