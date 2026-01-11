# Media storage setup (local, S3, or GCS)

This project now supports three storage backends for marketing images and other uploaded media:

- **Local (default):** files live under `media/` on disk. Good for quick dev, but not persistent on Railway dynos.
- **Amazon S3–compatible (S3, DigitalOcean Spaces, Cloudflare R2, etc.):** best for stable URLs and persistence.
- **Google Cloud Storage (GCS):** alternative cloud bucket option.

## Choosing a backend
Set `FILE_STORAGE_BACKEND` in your environment:

- `local` (default): keeps using the `media/` folder.
- `s3`: uses Django Storages with `S3Boto3Storage`.
- `gcs`: uses Django Storages with `GoogleCloudStorage`.

## Environment variables

### Common
- `FILE_STORAGE_BACKEND`: `local`, `s3`, or `gcs`.
- `MEDIA_ROOT`: (local only) absolute path where uploads are stored (example: `/app/media` on Railway volumes).
- `MEDIA_URL`: (local only) public URL prefix for uploads (default: `/media/`).
- `DJANGO_SERVE_MEDIA`: set to `true` if you want Django to serve media files directly (suitable for low traffic only).

### S3-compatible
- `AWS_STORAGE_BUCKET_NAME` (**required**)
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` (required unless your platform injects them automatically)
- `AWS_S3_REGION_NAME` (recommended)
- `AWS_S3_ENDPOINT_URL` (set this for non-AWS providers such as Railway’s S3-compatible buckets, R2, or Spaces)
- `AWS_S3_CUSTOM_DOMAIN` (optional; use your CDN/domain if configured)
- `AWS_S3_MEDIA_URL` (optional; overrides the computed media URL)

### GCS
- `GS_BUCKET_NAME` (**required**)
- `GOOGLE_APPLICATION_CREDENTIALS` (path to the service account JSON)
- `GS_PROJECT_ID` (optional)
- `GS_MEDIA_URL` (optional; overrides the default public URL)

## How it works
- `chateaurose/storage_settings.py` builds the `STORAGES` config at startup and raises a clear error if required variables are missing for the chosen backend.
- For S3/GCS, `MEDIA_URL` is derived from your bucket (or overridden by the `..._MEDIA_URL` env var). `MEDIA_ROOT` is disabled because files are served from the bucket.
- Static files remain served by WhiteNoise from `/static/`.

## Quick start on Railway (persistent images)
1. **Install deps on your Railway service:** ensure `django-storages` and `boto3` are installed (they are now in `requirements.txt`).
2. **Provision a bucket:** on AWS, R2, or Spaces. Grab the bucket name, region, endpoint, and access keys.
3. **Set env vars in Railway:**
   - `FILE_STORAGE_BACKEND=s3`
   - `AWS_STORAGE_BUCKET_NAME=<your bucket>`
   - `AWS_S3_REGION_NAME=<region>` (e.g., `eu-west-3`)
   - `AWS_S3_ENDPOINT_URL=<endpoint>` if using Spaces/R2 (e.g., `https://<account>.r2.cloudflarestorage.com`)
   - `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`
   - Optional: `AWS_S3_CUSTOM_DOMAIN` if you have a CDN in front.
4. **Upload images to the bucket:** either manually via the provider console or any S3 client. The admin forms and import command will store object keys automatically on upload.
5. **Verify:** visit an existing marketing page and confirm the image URLs point to your bucket domain.

## Quick start on Railway (volume-mounted media)
If you have a small amount of user-generated content and want to keep media on a Railway volume:
1. **Create a Railway volume** and mount it at `/app/media`.
2. **Set env vars in Railway:**
   - `FILE_STORAGE_BACKEND=local`
   - `MEDIA_ROOT=/app/media`
   - `DJANGO_SERVE_MEDIA=true` (optional, serves files through Django; acceptable for small traffic)
3. **Deploy and upload:** any `ImageField` uploads will land in the volume.
4. **Verify:** visit a record with an image and confirm the URL starts with `/media/`.

## Using committed static images for demos
If you need fixed images for beta demos without configuring a bucket:
1. Place your demo assets under `static/marketing/` and commit them.
2. In the Django admin (or import JSON), set the **Main image URL** or gallery **Image URL** to `/static/marketing/<filename>` (root-relative paths like this are accepted, as are full `https://` URLs).
3. Keep `FILE_STORAGE_BACKEND=local` (default). WhiteNoise will serve the committed static assets, so they stay stable even if the `media/` folder is cleared.

## Troubleshooting
- Missing bucket env vars: startup will raise a `ValueError` indicating the missing field.
- Wrong endpoint/custom domain: update `AWS_S3_ENDPOINT_URL` or `AWS_S3_CUSTOM_DOMAIN` and redeploy.
- GCS auth issues: confirm `GOOGLE_APPLICATION_CREDENTIALS` points to a mounted JSON key and the service account has storage access.

With this setup you can switch between local dev storage and cloud buckets just by changing environment variables—no code changes required.
