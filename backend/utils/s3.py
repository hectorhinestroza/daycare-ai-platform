"""AWS S3 utilities for photo storage.

All photos are stored with EXIF stripped, using UUID-only S3 keys (no PII).
All delivery to the frontend uses pre-signed URLs with a 1-hour expiry max.

Key format: photos/{center_id}/{child_id}/{date}/{uuid}.jpg
"""

import logging
from typing import Optional
from uuid import UUID

import boto3
from botocore.exceptions import ClientError

from backend.config import get_settings

logger = logging.getLogger(__name__)


def _get_s3_client():
    """Create a boto3 S3 client from app settings."""
    settings = get_settings()
    return boto3.client(
        "s3",
        region_name=settings.aws_s3_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )


def upload_photo(file_bytes: bytes, s3_key: str, content_type: str = "image/jpeg") -> str:
    """Upload EXIF-stripped photo bytes to S3.

    Args:
        file_bytes:   Clean JPEG bytes (already processed by process_incoming_photo).
        s3_key:       Full S3 key from build_photo_s3_key().
        content_type: MIME type (always image/jpeg after EXIF strip).

    Returns:
        The S3 key that was written.

    Raises:
        RuntimeError: If S3 upload fails or bucket is not configured.
    """
    settings = get_settings()

    if not settings.aws_s3_bucket:
        logger.warning(f"AWS_S3_BUCKET not configured — photo not uploaded. Key: {s3_key}")
        raise RuntimeError("S3 bucket not configured. Set AWS_S3_BUCKET in .env")

    client = _get_s3_client()

    try:
        client.put_object(
            Bucket=settings.aws_s3_bucket,
            Key=s3_key,
            Body=file_bytes,
            ContentType=content_type,
            # No ACL — bucket-level Block Public Access handles it
        )
        logger.info(f"Photo uploaded to s3://{settings.aws_s3_bucket}/{s3_key} ({len(file_bytes)} bytes)")
        return s3_key

    except ClientError as e:
        logger.error(f"S3 upload failed for {s3_key}: {e}")
        raise RuntimeError(f"S3 upload failed: {e}") from e


def generate_presigned_url(s3_key: str, expiry_seconds: int = 3600) -> Optional[str]:
    """Generate a temporary pre-signed URL for photo delivery.

    Legal requirement: max 1-hour expiry. Parents never get direct S3 access.

    Args:
        s3_key:         The S3 object key.
        expiry_seconds: URL lifetime in seconds (default & max: 3600 = 1 hour).

    Returns:
        Pre-signed URL string, or None if generation fails.
    """
    settings = get_settings()

    if not settings.aws_s3_bucket:
        logger.warning("AWS_S3_BUCKET not configured — cannot generate pre-signed URL.")
        return None

    # Enforce 1-hour max per legal requirement
    expiry_seconds = min(expiry_seconds, 3600)

    client = _get_s3_client()

    try:
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.aws_s3_bucket, "Key": s3_key},
            ExpiresIn=expiry_seconds,
        )
        return url

    except ClientError as e:
        logger.error(f"Failed to generate pre-signed URL for {s3_key}: {e}")
        return None


def delete_photo(s3_key: str) -> bool:
    """Delete a photo from S3 (used by 90-day retention job).

    Returns True if deleted successfully, False otherwise.
    """
    settings = get_settings()

    if not settings.aws_s3_bucket:
        return False

    client = _get_s3_client()

    try:
        client.delete_object(Bucket=settings.aws_s3_bucket, Key=s3_key)
        logger.info(f"Photo deleted from S3: {s3_key}")
        return True

    except ClientError as e:
        logger.error(f"S3 delete failed for {s3_key}: {e}")
        return False
