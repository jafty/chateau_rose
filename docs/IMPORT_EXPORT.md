# Data import/export with django-import-export

This project ships with [django-import-export](https://django-import-export.readthedocs.io/) configured in the Django admin to make it easy to bulk load content such as marketing pages, providers, services, and their relationships.

## Setup
1. Install dependencies (already pinned in `requirements.txt`):
   ```bash
   pip install -r requirements.txt
   ```
2. Run migrations and start the server:
   ```bash
   python manage.py migrate
   python manage.py createsuperuser  # if needed
   python manage.py runserver
   ```
3. Log in to the Django admin at `/admin/`.

### Editing providers manually
- In the **Providers** admin form, the **Zones** and **Services marketing** fields use Django's filterable dual-list widget. Use the search box above each list to narrow options, then click the arrows between the lists to move items in or out of the selection.
- The widget includes built-in JavaScript and CSS (loaded automatically by the admin), so zone/service choices persist when you save the provider.

## Where to import
Import/export actions are available from each admin list view that subclasses `ImportExportModelAdmin`.

### Booking app
| Model | Admin resource | Key columns |
| --- | --- | --- |
| Zones | `ZoneResource` | `id`, `name`, `slug` |
| Providers | `ProviderResource` | `id`, `name`, `description`, `contact_phone`, `contact_email`, `profile_image_url`, `works_in_salon_only`, `user_username` |
| Services | `ServiceResource` | `id`, `provider_id`, `name`, `slug`, `base_price_cents`, `hair_length_adjustments` (JSON), `meche_bonus_cents` |
| Provider photos | `ProviderPhotoResource` | `id`, `provider_id`, `image_url`, `caption`, `order` |
| Provider ↔ Zones | `ProviderZoneResource` | `id`, `provider_id`, `zone_slug` |
| Provider ↔ Marketing services | `ProviderMarketingServiceResource` | `id`, `provider_id`, `service_slug` |

### Interface app (marketing pages)
| Model | Admin resource | Key columns |
| --- | --- | --- |
| Marketing services (page templates) | `MarketingServiceResource` | `id`, `name`, `slug`, `intro`, `highlights` (JSON list), `main_image_url`, `meta_description` |
| Marketing zones (per-zone landing pages) | `MarketingZoneResource` | `id`, `zone_slug`, `intro`, `highlights` (JSON list), `hero_image_url`, `meta_description` |
| Marketing service gallery images | `MarketingServiceImageResource` | `id`, `service_slug`, `image_url`, `caption`, `order` |

## CSV/XLSX hints
- **Foreign keys**: `provider_id` expects a provider primary key; `zone_slug` and `service_slug` are unique slugs. `user_username` maps to the auth user’s username.
- **Images**: Provide `*_image_url` when you don’t want to upload files manually.
- **JSON fields**: Columns using `JSONWidget` (e.g., `highlights`, `hair_length_adjustments`) accept JSON text such as `[{"title": "Point fort", "description": ""}]` or `{ "court": 0, "long": 2000 }`.
- **IDs optional**: You can omit the `id` column when creating new rows; include it when updating existing data.

## Import workflow
1. From the relevant admin list page, click **Import**.
2. Upload a CSV/XLSX/JSON file. Ensure column names match the tables above.
3. Review the preview; resolve any validation errors (e.g., missing FK targets).
4. Confirm the import. Repeat for dependent models in this order to satisfy foreign keys:
   - Zones → Marketing services → Providers → Services → Marketing/zone pages → Relationship tables (Provider zones, Provider marketing services) → Photos/images.
5. Use **Export** from the same page to generate a template CSV before importing if desired.
