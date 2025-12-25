# HANDOFF

## Current state (infra & env)
- DB is selected via `DATABASE_URL` when set; otherwise falls back to SQLite `db.sqlite3` with a 600s pool. Hosts/CSRF are read from `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` (comma-separated), defaulting to localhost if unset. Media is served from `MEDIA_URL`/`MEDIA_ROOT` and will be ephemeral on container filesystems unless a persistent volume or remote storage is configured.
- Branching/deploys: the active branch is `work`; keep Railway pointing at the same branch to avoid reconfiguring hosts/CSRF/DB vars. If you deploy another branch intentionally, set those env vars there too and run `python manage.py migrate` on that environment.

## Domain use cases & entities
- **RequestHaircut** validates required fields, ensures service belongs to provider and zone is covered, checks hair length support, computes estimated price (base + hair-length adjustment + optional mèche bonus), creates a €10 auth, saves the booking, and notifies provider and client. Reminder scheduling is optional (can be `None`).
- **UpdateProposal** lets the provider overwrite price/date when not terminal, records proposal, timestamps `updated_at`, and notifies the client; rejects if wrong provider or terminal state.
- **FinalizeBooking** enforces a 48h guard, is idempotent on terminal states, captures or releases the auth depending on provider/client decisions, notifies both parties, and persists `updated_at`.
- **ExpireBooking** cancels after 48h from creation for SUBMITTED or PENDING_CLIENT_VALIDATION, releases auth, notifies provider/client, and updates the booking.
- **Entity**: `BookingRequest` carries ids, contact, location/date, hair_length, mèche flag, media paths, pricing (estimated/proposed), payment auth id, status, and timestamps.

## Interface wiring
- Request form is on provider detail: uploads are stored under `bookings/current/` and `bookings/inspiration/`, then `request_haircut` is called with shared adapters (repo, provider catalog, payment stub, notifier stub) and a real clock.
- Provider actions require authenticated staff; `provider_action` calls `finalize_booking` with actor=`provider`. Client actions call `finalize_booking` with actor=`client`.
- SEO pages: service pages filter providers by service slug; service+city pages add a zone filter (city + its districts); service+city+district pages scope to a specific district. Slugs and names come from `interface/seo.py` (services, cities, districts).

## Data model & admin
- Services belong to a provider and include `slug`, `base_price_cents`, `hair_length_adjustments` (JSON mapping length -> delta cents), and `meche_bonus_cents`. Zones have a unique slug; ProviderZone links coverage. ProviderPhoto stores gallery images; Provider has an optional profile image.
- Zone admin slug choices are constrained to the SEO city/district list and auto-fill the display name to avoid off-list entries.

## SEO taxonomy (routing keys)
- Services (slugs): tresses, locks, tissage, vanilles, soins, perruques, defrisage-assouplissement, coloration-meches, coiffure-enfant-afro.
- Cities: Toulouse, Colomiers, Tournefeuille, Blagnac, Muret, Cugnaux, Plaisance-du-Touch, Balma, L'Union, Ramonville-Saint-Agne, Saint-Orens-de-Gameville, Castanet-Tolosan, Portet-sur-Garonne, Saint-Jean, Aucamville.
- Districts (Toulouse): Capitole; Arnaud-Bernard; Jean-Jaurès; Saint-Cyprien; Les Minimes; Compans/Amidonniers; Les Chalets/Bayard; Carmes/Ozenne; Saint-Michel/Empalot/Saint-Agne; Rangueil/Saouzelong/Pech David; Busca/Terre Cabade; Pont des Demoiselles/Ormeau; Côte Pavée/Guilheméry; Roseraie/Jolimont; Bonnefoy; Sept Deniers; Patte-d'Oie/Casselardit; Fontaine-Lestang/Mermoz; Reynerie/Bagatelle/Faourette; Mirail/Université/Basso Cambo; Borderouge/Croix-Daurade; Lalande; Les Pradettes; Lardenne/Saint-Simon; Sesquières.

## Tests to run
- Domain suite: `pytest chateaurose/domain/tests` (in-memory ports only).
- Interface smoke: `python manage.py test interface.tests.test_service_pages interface.tests.test_request_uploads` (requires Django settings; uses in-memory media storage by default).

## Known gaps / next steps
- Media persistence: uploads are ephemeral on container filesystems; move to a volume or object storage for durable files. For hero/marketing visuals, commit static assets or serve from a CDN so staging pages aren't empty between deploys.
- Seed data: create Zones (using allowed slugs), Providers, Services (with hair-length adjustments and mèche bonus), ProviderZones, and staff provider users for actions.
- Ensure migrations are run on each Railway environment after model changes.
