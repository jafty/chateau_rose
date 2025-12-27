import pytest

from chateaurose.domain.services.marketing_content import (
    CityContent,
    GalleryImage,
    MarketingContent,
    OverrideContent,
    ServiceContent,
    build_marketing_content,
)


def test_city_injected_when_no_override_highlights():
    service = ServiceContent(name="Tresses", highlights=["Pose soignée"], intro="Base intro")
    city = CityContent(name="Toulouse")

    content: MarketingContent = build_marketing_content(service=service, city=city)

    assert content.highlights == ["Pose soignée (Toulouse)"]
    assert "Toulouse" in content.city_intro


def test_override_highlights_and_intro_take_precedence():
    service = ServiceContent(name="Locks", highlights=["Rapide"])
    city = CityContent(name="Toulouse")
    override = OverrideContent(intro="Intro ville", highlights=["Spécialiste"])

    content = build_marketing_content(service=service, city=city, override=override)

    assert content.intro == "Intro ville"
    assert content.city_intro == "Intro ville"
    assert content.highlights == ["Spécialiste"]


def test_fallback_highlights_when_none_and_city_given():
    service = ServiceContent(name="Vanilles", highlights=[])
    city = CityContent(name="Paris")

    content = build_marketing_content(service=service, city=city)

    assert all("Paris" in highlight for highlight in content.highlights)
    assert len(content.highlights) >= 1


def test_meta_description_priority_and_fallbacks():
    service = ServiceContent(name="Tissage", meta_description="Meta service")
    city = CityContent(name="Lyon")
    override = OverrideContent(meta_description="Meta override")

    content = build_marketing_content(service=service, city=city, override=override)
    assert content.meta_description == "Meta override"

    content_without_override = build_marketing_content(service=service, city=city)
    assert content_without_override.meta_description == "Meta service"

    service_no_meta = ServiceContent(name="Tissage")
    city_no_meta = CityContent(name="Marseille")
    content_with_fallback = build_marketing_content(service=service_no_meta, city=city_no_meta)
    assert "Marseille" in content_with_fallback.meta_description


def test_hero_and_gallery_precedence():
    service = ServiceContent(
        name="Tresses",
        main_image="service-hero.jpg",
        gallery=[GalleryImage(url="s1.jpg"), GalleryImage(url="s2.jpg")],
    )
    city = CityContent(name="Toulouse", main_image="city-hero.jpg")
    override = OverrideContent(
        main_image="override-hero.jpg",
        gallery=[GalleryImage(url="o1.jpg", caption="Override")],
    )

    content = build_marketing_content(service=service, city=city, override=override)
    assert content.hero_image == "override-hero.jpg"
    assert [img.url for img in content.gallery] == ["o1.jpg"]

    content_no_override = build_marketing_content(service=service, city=city)
    assert content_no_override.hero_image == "city-hero.jpg"
    assert [img.url for img in content_no_override.gallery] == ["s1.jpg", "s2.jpg"]

    content_service_only = build_marketing_content(service=service)
    assert content_service_only.hero_image == "service-hero.jpg"
    assert [img.url for img in content_service_only.gallery] == ["s1.jpg", "s2.jpg"]


def test_district_meta_description_mentions_district_when_no_override():
    service = ServiceContent(name="Tresses")
    city = CityContent(name="Toulouse")

    content = build_marketing_content(service=service, city=city, district_name="Compans")

    assert "Compans" in content.meta_description
    assert any("Compans" in highlight for highlight in content.highlights)
