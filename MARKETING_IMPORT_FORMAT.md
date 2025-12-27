# Marketing content import format

This importer ingests a JSON file to create or update marketing services, cities, districts, and optional service+city overrides. Use it with the management command:

```bash
python manage.py import_marketing_content path/to/file.json
```

### How to run the import (step by step)
1. Prepare your JSON file following the format below.
2. Ensure you are in the project directory (where `manage.py` lives).
3. Run `python manage.py import_marketing_content path/to/file.json`.
4. If validation fails, nothing is persisted; fix the reported errors and re-run.
5. On success, services/cities/districts/overrides and their galleries are upserted in a single transaction.

> The import does **not** download or upload images. It only stores the paths/URLs you provide. See “Image handling” below.

## Top-level structure

```json
{
  "services": [ { /* service objects */ } ]
}
```

* `services` — **required** list with at least one entry.
* Only JSON is supported by the importer.

## Service object

```json
{
  "slug": "tresses",          // required, unique per service
  "name": "Tresses",          // required
  "intro": "Base intro",      // optional string
  "highlights": ["Rapide"],   // optional list of strings
  "main_image": "service.jpg",// optional string (URL/path)
  "main_image_url": "https://cdn.example.com/tresses-hero.jpg", // optional absolute URL for static assets
  "meta_description": "Meta", // optional string
  "gallery": ["g1.jpg"],      // optional list of strings
  "cities": [ { /* city objects */ } ] // optional list
}
```

Rules:
- `slug` and `name` must be non-empty strings; duplicate service slugs are rejected.
- `highlights` and `gallery` must be lists of strings; any other type raises validation errors.
- `intro`, `main_image`, `main_image_url`, and `meta_description` are optional; blanks become empty strings/`null` internally.

## City object (within a service)

```json
{
  "slug": "toulouse",            // required
  "name": "Toulouse",            // required
  "intro": "Ville",              // optional string
  "main_image": "city.jpg",      // optional string
  "main_image_url": "https://cdn.example.com/city.jpg", // optional absolute URL for static assets
  "meta_description": "City meta",// optional string
  "districts": [ { /* district objects */ } ], // optional list
  "override": { /* service+city override */ }  // optional object
}
```

Rules:
- City slugs must be consistent across services; conflicting definitions (different names, intro, main image, or meta description) fail validation.
- `districts` must be a list when present.

## District object (within a city)

```json
{
  "slug": "compans",               // required
  "name": "Compans",               // required
  "intro": "Quartier",             // optional string
  "meta_description": "Quartier meta" // optional string
}
```

Rules:
- District slugs are unique per city; conflicting name/intro/meta definitions for the same city+district combination raise errors.

## Service+city override (optional)

Overrides let you specialize a service page for a given city without redefining the whole service.

```json
{
  "intro": "Intro ville",             // optional string
  "highlights": ["Local"],            // optional list of strings
  "main_image": "override.jpg",       // optional string
  "main_image_url": "https://cdn.example.com/override.jpg", // optional absolute URL for static assets
  "gallery": ["o1.jpg"],              // optional list of strings (URL/path)
  "meta_description": "Override meta" // optional string
}
```

Rules:
- `highlights` and `gallery` must be lists of strings when provided.
- If no override is present, the importer falls back to the base service content for that city.

## Image handling

- All image fields (`main_image`, `main_image_url`, and entries in `gallery`) are stored as-is in the database; the importer does not fetch or upload files.
- Provide either:
  - A relative path within your media storage (e.g., `marketing/services/main/tresses.jpg`) **after** you have uploaded the file to `MEDIA_ROOT`/your storage bucket, or
  - An absolute URL to an already-hosted asset (e.g., `https://cdn.example.com/tresses/hero.jpg`).
- Upload the images to your storage (S3, local `MEDIA_ROOT`, etc.) **before** running the import so the stored paths already resolve at runtime.
- If you later move images, rerun the import with the updated paths/URLs to keep the database in sync.
- When both `main_image` and `main_image_url` are provided, the importer preserves the URL field so templates can use a stable asset even if media storage is not populated (useful for demos/beta previews).

## Complete example

```json
{
  "services": [
    {
      "slug": "tresses",
      "name": "Tresses",
      "intro": "Base intro",
      "highlights": ["Rapide", "Protecteur"],
      "main_image_url": "https://cdn.example.com/tresses/hero.jpg",
      "meta_description": "Réserve des tresses facilement.",
      "gallery": [
        "https://cdn.example.com/tresses/gallery1.jpg",
        "https://cdn.example.com/tresses/gallery2.jpg"
      ],
      "cities": [
        {
          "slug": "toulouse",
          "name": "Toulouse",
          "intro": "Coiffures afro à Toulouse.",
          "main_image_url": "https://cdn.example.com/cities/toulouse.jpg",
          "meta_description": "Coiffures afro à Toulouse en centre-ville.",
          "districts": [
            {
              "slug": "compans",
              "name": "Compans",
              "intro": "Rendez-vous près de Compans-Caffarelli.",
              "meta_description": "Coiffure afro à Compans-Caffarelli."
            }
          ],
          "override": {
            "intro": "Spécial Toulouse : nos tresses à deux pas du Capitole.",
            "highlights": ["Proches métro", "Stylistes locaux"],
            "main_image_url": "https://cdn.example.com/tresses/toulouse/hero.jpg",
            "gallery": [
              "https://cdn.example.com/tresses/toulouse/1.jpg",
              "https://cdn.example.com/tresses/toulouse/2.jpg"
            ],
            "meta_description": "Tresses à Toulouse : réservation rapide et locale."
          }
        }
      ]
    },
    {
      "slug": "vanilles",
      "name": "Vanilles",
      "gallery": ["https://cdn.example.com/vanilles/1.jpg"]
    }
  ]
}
```

## Validation recap

- The importer stops and reports validation errors (without persisting anything) when it encounters:
  - Missing/blank `slug` or `name` on services, cities, or districts.
  - Duplicate service slugs.
  - Conflicting city or district definitions across services.
  - Non-list `highlights`/`gallery` fields.
- Payloads that are not valid JSON or that lack a top-level `services` list with at least one entry.

## Tips for bulk uploads

- Keep slugs URL-friendly (lowercase, hyphenated).
- Host images at stable URLs accessible by your frontend.
- Start with a small file and run the import command to catch validation errors early before scaling to a larger tree of services/cities.

## Hosting static images (SEO-friendly approach)

- **Prefer your own domain or CDN**: For SEO and reliability, serve assets from your main domain or a CDN subdomain you control. This keeps page speed and caching under your control and avoids hotlinking penalties from third-party hosts.
- **Using the `static/` folder:** You can commit demo images to `static/marketing/...` and deploy them with your static assets. After running the app (or `collectstatic` in production), the images are reachable at `https://<your-domain>/static/marketing/<file>` (or `http://localhost:8000/static/marketing/<file>` in dev). Paste that full URL into `main_image_url` or gallery URLs in the admin/import JSON.
- **GitHub-hosted images:** Technically you can hotlink to `raw.githubusercontent.com`, but it is slower, may change without notice, and is less SEO-friendly than serving from your own static domain. Prefer your own static hosting whenever possible.
- **Checklist to get a URL quickly:**
  1. Place your image under `static/marketing/` (e.g., `static/marketing/hero.jpg`).
  2. Run the site locally (`python manage.py runserver`) and visit `http://localhost:8000/static/marketing/hero.jpg` to confirm it loads.
  3. Use that full URL in the admin `Main image URL` or in the import JSON. In production, swap the host with your live domain once deployed.
