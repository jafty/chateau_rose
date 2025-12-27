# Code overview (ELI5)

## Domain layer (`chateaurose/domain`)
The domain folder holds the business rules in pure Python, independent from Django.

### Entities
- **BookingRequest** (`entities/booking.py`): a dataclass that represents a haircut request with client contact, chosen service, location, pictures, price estimates, payment authorization, status, and timestamps.

### Services
- **marketing_content** (`services/marketing_content.py`): builds the text and media for service pages. It merges default service copy with city-specific overrides and district names, picks a hero image, chooses a gallery, and computes a meta description so each city page stays unique. The `highlights` it produces are short bullet points that reassure visitors (e.g., fast response, clear brief, specialists available) and can be localized with the city name.

### Use cases
- **request_haircut**: validates a new request, checks the provider offers the service and covers the zone, estimates price, creates a booking ID, authorizes payment, saves the booking, notifies provider and client, and schedules reminders.
- **update_proposal**: lets a provider propose a new price/date, moves the booking to “pending client validation,” and notifies the client.
- **finalize_booking**: lets provider or client confirm/refuse; captures or releases the payment authorization, sends notifications, and guards against invalid states or late confirmations.
- **expire_booking**: auto-cancels requests older than 48h, releases payment auth, and sends expiry notifications.
- **send_reminder**: after 24h without response, pings the provider about the pending request.

### Repositories (ports)
- **Repository / ReadOnlyRepository** (`repositories/base.py`): abstract contracts describing CRUD/list/find operations without assuming storage.
- **BookingRepository** (`repositories/booking.py`): port dedicated to persisting `BookingRequest` aggregates.

### Gateways (ports)
- **payments.py**: contract for creating/capturing/releasing payment authorizations.
- **notifier.py**: contract for sending notifications to providers/clients.
- **reminder.py**: contract for scheduling reminders.
- **clock.py**: contract for time access.

### Infrastructure adapters (`chateaurose/infrastructure`)
Concrete implementations of the ports for the Django app:
- **booking_repository.py**: stores and retrieves bookings via Django models.
- **provider_catalog.py**: reads provider/services/zones from Django models for validation and price computations.
- **payment_stub.py**, **notifier_stub.py**, **reminder_stub.py**: simple stubs used by the web app to simulate payments and messaging.

## Django layer

### Booking app models (`booking/models.py`)
- **Provider**: hair artist with contact info and profile image.
- **Zone**: city/area slug used to match provider coverage.
- **Service**: offering attached to a provider with base price, hair-length adjustments, and optional “mèche” bonus.
- **ProviderPhoto**: gallery images for a provider.
- **ProviderZone**: mapping of which zones a provider serves.
- **Booking**: persisted booking linked to provider/service with client details, status, pricing, and proposal fields.

### Marketing models (`interface/models.py`)
- **MarketingService**: public-facing service with slug, intro, highlight bullets, main hero image, and meta description.
- **MarketingServiceImage**: ordered gallery images for a `MarketingService`.
- **MarketingCity**: city with slug, intro, hero image, and meta description for localized pages.
- **MarketingDistrict**: neighborhood tied to a city with optional intro/meta text.
- **MarketingServiceCity**: per service+city overrides for intro, highlights, hero image, and meta description.
- **MarketingServiceCityImage**: ordered gallery images specific to a service+city override.

### Views (`interface/views.py`)
- **home**: shows featured marketing services, providers, zones, and cities for quick navigation.
- **provider_list**: lists all providers.
- **provider_detail**: displays a provider, their services/zones, and handles booking submissions through the `request_haircut` use case.
- **provider_action / client_action**: finalize or cancel bookings via the `finalize_booking` use case depending on who acts.
- **service_page**: renders a marketing service using the domain marketing content builder for default copy/images.
- **service_city_page**: renders the service localized to a city, applying any `MarketingServiceCity` overrides and selecting providers covering that city/district.
- **service_city_district_page**: same as above but scoped to a district; falls back through district/city/service images.
- **about**: static about/FAQ page fed by marketing services for quick links.

### Admin
Django admin exposes all marketing models with inlines for galleries so editors can manage content without code changes (see `interface/admin.py`).

## How to edit copy & media
- Use Django admin to edit Marketing Service/City/District and Service+City overrides (intros, highlights, hero images, galleries, meta descriptions).
- Provider/service/zone coverage is also editable in admin via the booking app models.
- The domain marketing content builder uses these values to generate page content, so updates in admin flow straight to the rendered pages.
