# Zones, services, and filters

## Zones are city or district slugs (Toulouse-first)
- Service SEO taxonomy defines cities and Toulouse districts up front. Slugs are reused as `Zone.slug` values when creating coverage entries for providers. Toulouse is the default fallback location in marketing copy and meta descriptions when no city is provided.
- Admin zone choices are constrained to the SEO city/district list, and names auto-fill from the slug to keep a single list of allowed zones.

## How providers are filtered on service pages
- **Service page** (`/services/<service>/`): shows all providers offering the service, regardless of zone.
- **Service + city page**: filters providers by service **and** any zone whose slug matches the city or one of its districts, so Toulouse + its districts surface providers covering any of those zones.
- **Service + city + district page**: filters providers by service **and** the specific district slug.
- City-level pages populate district chips only when the city has districts; otherwise the district selector is omitted.

## Assigning services and zones to providers
- To make a provider appear on filtered pages, create `Service` rows for each marketing service slug they offer, then add `ProviderZone` rows pointing to `Zone` entries whose slugs match the allowed city/district list (e.g., `toulouse`, `capitole`).
- A provider appears on a service page when they offer that service; on a service+city page when they cover the city or one of its districts; and on a service+city+district page only when they cover that exact district.
