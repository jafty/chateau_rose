from chateaurose.domain.services.marketing_content import (
    DEFAULT_LOCATION_INTRO,
    GalleryImage,
    MarketingContent,
    ServiceContent,
    build_marketing_content,
)


def test_highlights_and_intro_include_location_when_given():
    service = ServiceContent(name="Tresses", highlights=["Pose soignée"], intro="Base intro")

    content: MarketingContent = build_marketing_content(service=service, location_name="Toulouse")

    assert content.intro == "Base intro"
    assert "Toulouse" in content.location_intro
    assert all("Toulouse" in h for h in content.highlights)


def test_highlights_with_location_are_not_duplicated():
    service = ServiceContent(name="Tresses", highlights=["Pose soignée (Toulouse)"])

    content = build_marketing_content(service=service, location_name="Toulouse")

    assert content.highlights == ["Pose soignée (Toulouse)"]


def test_location_intro_focuses_on_availability():
    service = ServiceContent(name="Locks", intro="Intro sans localisation")

    content = build_marketing_content(service=service, location_name="Lyon")

    assert content.intro == "Intro sans localisation"
    assert content.location_intro.startswith("Disponible à Lyon")


def test_fallbacks_when_service_missing_fields():
    service = ServiceContent(name="Locks")

    content = build_marketing_content(service=service)

    assert content.hero_image is None
    assert content.gallery == []
    assert content.location_intro == DEFAULT_LOCATION_INTRO
    assert "Toulouse" in content.meta_description


def test_gallery_and_hero_forwarded():
    service = ServiceContent(
        name="Vanilles",
        main_image="service-hero.jpg",
        gallery=[GalleryImage(url="s1.jpg"), GalleryImage(url="s2.jpg")],
    )

    content = build_marketing_content(service=service, location_name="Marseille")

    assert content.hero_image == "service-hero.jpg"
    assert [img.url for img in content.gallery] == ["s1.jpg", "s2.jpg"]
    assert "Marseille" in content.meta_description
