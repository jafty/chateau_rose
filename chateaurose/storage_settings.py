from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, MutableMapping, Optional


@dataclass
class StorageSettings:
    storages: dict
    media_url: str
    media_root: Optional[Path]
    extra_settings: dict


def build_storage_settings(env: Mapping[str, str], base_dir: Path) -> StorageSettings:
    backend = env.get("FILE_STORAGE_BACKEND", "local").lower()
    storages: MutableMapping[str, dict] = {
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"}
    }

    if backend == "local":
        storages["default"] = {"BACKEND": "django.core.files.storage.FileSystemStorage"}
        return StorageSettings(storages=dict(storages), media_url="/media/", media_root=base_dir / "media", extra_settings={})

    if backend == "s3":
        bucket = env.get("AWS_STORAGE_BUCKET_NAME")
        if not bucket:
            raise ValueError("AWS_STORAGE_BUCKET_NAME is required when FILE_STORAGE_BACKEND=s3")
        custom_domain = env.get("AWS_S3_CUSTOM_DOMAIN")
        endpoint_url = env.get("AWS_S3_ENDPOINT_URL")
        region = env.get("AWS_S3_REGION_NAME")
        media_url = env.get("AWS_S3_MEDIA_URL")
        if not media_url:
            if custom_domain:
                media_url = f"https://{custom_domain}/"
            elif endpoint_url:
                media_url = f"{endpoint_url.rstrip('/')}/{bucket}/"
            else:
                media_url = f"https://{bucket}.s3.amazonaws.com/"

        extra_settings = {
            "AWS_STORAGE_BUCKET_NAME": bucket,
        }
        if region:
            extra_settings["AWS_S3_REGION_NAME"] = region
        if endpoint_url:
            extra_settings["AWS_S3_ENDPOINT_URL"] = endpoint_url
        access_key = env.get("AWS_ACCESS_KEY_ID")
        secret_key = env.get("AWS_SECRET_ACCESS_KEY")
        if access_key and secret_key:
            extra_settings["AWS_ACCESS_KEY_ID"] = access_key
            extra_settings["AWS_SECRET_ACCESS_KEY"] = secret_key
        if custom_domain:
            extra_settings["AWS_S3_CUSTOM_DOMAIN"] = custom_domain

        storages["default"] = {"BACKEND": "storages.backends.s3boto3.S3Boto3Storage"}
        return StorageSettings(storages=dict(storages), media_url=media_url, media_root=None, extra_settings=extra_settings)

    if backend == "gcs":
        bucket = env.get("GS_BUCKET_NAME")
        if not bucket:
            raise ValueError("GS_BUCKET_NAME is required when FILE_STORAGE_BACKEND=gcs")
        media_url = env.get("GS_MEDIA_URL") or f"https://storage.googleapis.com/{bucket}/"
        extra_settings = {"GS_BUCKET_NAME": bucket}
        credentials_file = env.get("GOOGLE_APPLICATION_CREDENTIALS")
        if credentials_file:
            extra_settings["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_file
        project_id = env.get("GS_PROJECT_ID")
        if project_id:
            extra_settings["GS_PROJECT_ID"] = project_id

        storages["default"] = {"BACKEND": "storages.backends.gcloud.GoogleCloudStorage"}
        return StorageSettings(storages=dict(storages), media_url=media_url, media_root=None, extra_settings=extra_settings)

    raise ValueError("Unsupported FILE_STORAGE_BACKEND. Use 'local', 's3', or 'gcs'.")
