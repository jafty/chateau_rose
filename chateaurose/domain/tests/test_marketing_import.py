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
                "cities": [
                    {
                        "slug": "toulouse",
                        "name": "Toulouse",
                        "intro": "Ville",
                        "main_image": "city.jpg",
                        "main_image_url": "https://static.example.com/city.jpg",
                        "meta_description": "City meta",
                        "districts": [
                            {
                                "slug": "compans",
                                "name": "Compans",
                                "intro": "Quartier",
                                "meta_description": "Quartier meta",
                            }
                        ],
                        "override": {
                            "intro": "Intro ville",
                            "highlights": ["Local"],
                            "main_image": "override.jpg",
                            "main_image_url": "https://static.example.com/override.jpg",
                            "gallery": ["o1.jpg"],
                            "meta_description": "Override meta",
                        },
                    }
                ],
            }
        ]
    }


def test_valid_payload_builds_bundle_and_calls_repository():
    repository = InMemoryMarketingContentRepository()
    raw = json.dumps(_sample_payload())

    result = import_marketing_content.execute(
        raw_content=raw,
        repository=repository,
        format="json",
    )

    assert repository.calls == 1
    bundle = repository.received_bundle
    assert len(bundle.services) == 1
    assert bundle.services[0].slug == "tresses"
    assert bundle.services[0].main_image_url == "https://static.example.com/service.jpg"
    assert len(bundle.cities) == 1
    assert bundle.cities[0].slug == "toulouse"
    assert bundle.cities[0].main_image_url == "https://static.example.com/city.jpg"
    assert len(bundle.cities[0].districts) == 1
    assert len(bundle.service_city_overrides) == 1
    override = bundle.service_city_overrides[0]
    assert override.city_slug == "toulouse"
    assert override.service_slug == "tresses"
    assert override.main_image_url == "https://static.example.com/override.jpg"
    assert result.services_count == 1
    assert result.cities_count == 1
    assert result.districts_count == 1
    assert result.overrides_count == 1


def test_duplicate_service_slug_rejected():
    payload = _sample_payload()
    payload["services"].append({
        "slug": "tresses",
        "name": "Tresses bis",
    })
    repository = InMemoryMarketingContentRepository()

    with pytest.raises(ValidationError):
        import_marketing_content.execute(
            raw_content=json.dumps(payload),
            repository=repository,
            format="json",
        )

    assert repository.calls == 0


def test_conflicting_city_definition_rejected():
    payload = _sample_payload()
    payload["services"].append(
        {
            "slug": "vanilles",
            "name": "Vanilles",
            "cities": [
                {
                    "slug": "toulouse",
                    "name": "TLS",
                }
            ],
        }
    )
    repository = InMemoryMarketingContentRepository()

    with pytest.raises(ValidationError):
        import_marketing_content.execute(
            raw_content=json.dumps(payload),
            repository=repository,
            format="json",
        )

    assert repository.calls == 0


def test_invalid_highlights_type_rejected_before_persisting():
    payload = _sample_payload()
    payload["services"][0]["highlights"] = "Rapide"
    repository = InMemoryMarketingContentRepository()

    with pytest.raises(ValidationError):
        import_marketing_content.execute(
            raw_content=json.dumps(payload),
            repository=repository,
            format="json",
        )

    assert repository.calls == 0
