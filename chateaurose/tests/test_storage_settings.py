from pathlib import Path
import sys

def _ensure_project_root_on_path():
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


_ensure_project_root_on_path()

import pytest

from chateaurose.storage_settings import build_storage_settings


@pytest.fixture
def base_dir(tmp_path: Path) -> Path:
    return tmp_path


def test_local_storage_defaults(base_dir: Path):
    settings = build_storage_settings({}, base_dir)
    assert settings.storages["default"]["BACKEND"] == "django.core.files.storage.FileSystemStorage"
    assert settings.media_url == "/media/"
    assert settings.media_root == base_dir / "media"
    assert settings.extra_settings == {}


def test_s3_storage_with_custom_domain(base_dir: Path):
    env = {
        "FILE_STORAGE_BACKEND": "s3",
        "AWS_STORAGE_BUCKET_NAME": "demo-bucket",
        "AWS_S3_CUSTOM_DOMAIN": "cdn.example.com",
        "AWS_S3_REGION_NAME": "eu-west-3",
    }
    settings = build_storage_settings(env, base_dir)
    assert settings.storages["default"]["BACKEND"] == "storages.backends.s3boto3.S3Boto3Storage"
    assert settings.media_url == "https://cdn.example.com/"
    assert settings.extra_settings["AWS_STORAGE_BUCKET_NAME"] == "demo-bucket"
    assert (
        settings.extra_settings["AWS_S3_OBJECT_PARAMETERS"]["CacheControl"]
        == "max-age=31536000, s-maxage=31536000, immutable"
    )
    assert settings.extra_settings["AWS_QUERYSTRING_AUTH"] is False
    assert settings.extra_settings["AWS_S3_REGION_NAME"] == "eu-west-3"
    assert settings.extra_settings["AWS_S3_CUSTOM_DOMAIN"] == "cdn.example.com"
    assert settings.media_root is None


def test_s3_storage_requires_bucket(base_dir: Path):
    with pytest.raises(ValueError):
        build_storage_settings({"FILE_STORAGE_BACKEND": "s3"}, base_dir)


def test_gcs_storage_defaults(base_dir: Path):
    env = {"FILE_STORAGE_BACKEND": "gcs", "GS_BUCKET_NAME": "demo-bucket"}
    settings = build_storage_settings(env, base_dir)
    assert settings.storages["default"]["BACKEND"] == "storages.backends.gcloud.GoogleCloudStorage"
    assert settings.media_url == "https://storage.googleapis.com/demo-bucket/"
    assert settings.extra_settings["GS_BUCKET_NAME"] == "demo-bucket"
    assert settings.media_root is None


def test_gcs_storage_requires_bucket(base_dir: Path):
    with pytest.raises(ValueError):
        build_storage_settings({"FILE_STORAGE_BACKEND": "gcs"}, base_dir)
