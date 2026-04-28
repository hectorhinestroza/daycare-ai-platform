"""Tests forPhoto EXIF Stripping + Secure S3 Storage.

Verifies:
- GPS EXIF data is completely stripped from photos
- ALL EXIF metadata is stripped (not just GPS)
- S3 key contains no child name or PII
- Consent gate blocks before any bytes are processed
- Invalid file type (non-JPEG/PNG) → raises ValueError
- File > 10MB → raises ValueError
- Returned bytes are valid JPEG
"""
import io
import re
import uuid
from unittest.mock import MagicMock, patch

import piexif
import pytest
from PIL import Image

from backend.utils.consent_gate import ConsentGateException
from backend.utils.photo import build_photo_s3_key, process_incoming_photo

# ─── EXIF test image helpers ──────────────────────────────────


def _make_jpeg_with_gps_exif() -> bytes:
    """Create a minimal JPEG with GPS EXIF metadata using Pillow."""

    # Create a tiny red image
    img = Image.new("RGB", (10, 10), color=(255, 0, 0))

    # Build fake EXIF with GPS data
    exif_dict = {
        "GPS": {
            piexif.GPSIFD.GPSLatitudeRef: b"N",
            piexif.GPSIFD.GPSLatitude: ((40, 1), (44, 1), (5500, 100)),
            piexif.GPSIFD.GPSLongitudeRef: b"W",
            piexif.GPSIFD.GPSLongitude: ((73, 1), (59, 1), (4500, 100)),
        },
        "0th": {
            piexif.ImageIFD.Make: b"Apple",
            piexif.ImageIFD.Model: b"iPhone 15 Pro",
        },
    }
    exif_bytes = piexif.dump(exif_dict)

    output = io.BytesIO()
    img.save(output, format="JPEG", exif=exif_bytes)
    return output.getvalue()


def _make_plain_jpeg() -> bytes:
    """Create a minimal JPEG with no EXIF."""

    img = Image.new("RGB", (10, 10), color=(0, 255, 0))
    output = io.BytesIO()
    img.save(output, format="JPEG")
    return output.getvalue()


def _make_png() -> bytes:
    """Create a minimal PNG."""

    img = Image.new("RGB", (10, 10), color=(0, 0, 255))
    output = io.BytesIO()
    img.save(output, format="PNG")
    return output.getvalue()


def _has_exif(jpeg_bytes: bytes) -> bool:
    """Return True if the JPEG bytes contain an EXIF APP1 segment."""
    # EXIF in JPEG is an APP1 marker (0xFFE1) containing "Exif\x00\x00"
    return b"Exif" in jpeg_bytes or b"\xff\xe1" in jpeg_bytes


# ─── Tests: process_incoming_photo ────────────────────────────


class TestProcessIncomingPhotoExif:
    """EXIF stripping requirements."""

    def test_strips_gps_exif_from_jpeg(self):
        """GPS EXIF must be completely absent from the output bytes."""

        raw_bytes = _make_jpeg_with_gps_exif()
        # Confirm our test image actually has EXIF before stripping
        assert _has_exif(raw_bytes), "Test setup failed: input JPEG has no EXIF"

        mock_db = MagicMock()
        # Consent gate passes (returns a mock child)
        with patch("backend.utils.photo.get_child_for_processing", return_value=MagicMock()):
            result = process_incoming_photo(
                raw_bytes=raw_bytes,
                child_id=uuid.uuid4(),
                center_id=uuid.uuid4(),
                db=mock_db,
                environment="development",
            )

        assert not _has_exif(result), "EXIF still present in output — stripping failed"

    def test_strips_device_metadata(self):
        """Device make/model EXIF must be absent from output."""

        raw_bytes = _make_jpeg_with_gps_exif()

        mock_db = MagicMock()
        with patch("backend.utils.photo.get_child_for_processing", return_value=MagicMock()):
            result = process_incoming_photo(
                raw_bytes=raw_bytes,
                child_id=uuid.uuid4(),
                center_id=uuid.uuid4(),
                db=mock_db,
                environment="development",
            )

        # Apple and iPhone should not appear in output bytes
        assert b"Apple" not in result
        assert b"iPhone" not in result

    def test_output_is_valid_jpeg(self):
        """Stripped output must be a valid JPEG (decodable by Pillow)."""

        raw_bytes = _make_jpeg_with_gps_exif()
        mock_db = MagicMock()

        with patch("backend.utils.photo.get_child_for_processing", return_value=MagicMock()):
            result = process_incoming_photo(
                raw_bytes=raw_bytes,
                child_id=uuid.uuid4(),
                center_id=uuid.uuid4(),
                db=mock_db,
                environment="development",
            )

        # Pillow must be able to open it without error
        img = Image.open(io.BytesIO(result))
        assert img.format == "JPEG"

    def test_accepts_png_input(self):
        """PNG input must be accepted and converted to EXIF-free JPEG."""

        raw_bytes = _make_png()
        mock_db = MagicMock()

        with patch("backend.utils.photo.get_child_for_processing", return_value=MagicMock()):
            result = process_incoming_photo(
                raw_bytes=raw_bytes,
                child_id=uuid.uuid4(),
                center_id=uuid.uuid4(),
                db=mock_db,
                environment="development",
            )

        assert result is not None
        assert not _has_exif(result)


class TestProcessIncomingPhotoConsentGate:
    """Consent gate must fire before any photo bytes are processed."""

    def test_raises_consent_gate_exception_when_no_consent_in_production(self):
        """ConsentGateException raised before any S3 write when gate blocks."""

        raw_bytes = _make_plain_jpeg()
        mock_db = MagicMock()

        # Gate returns None → no consent in production
        with patch("backend.utils.photo.get_child_for_processing", return_value=None):
            with pytest.raises(ConsentGateException):
                process_incoming_photo(
                    raw_bytes=raw_bytes,
                    child_id=uuid.uuid4(),
                    center_id=uuid.uuid4(),
                    db=mock_db,
                    environment="production",
                )

    def test_consent_check_happens_before_image_decode(self):
        """Consent gate must be called first — before Pillow processes anything."""

        # Invalid bytes — if consent gate fires first, we get ConsentGateException
        # If consent gate fires after decode, we'd get a different error
        garbage_bytes = b"not a real image at all"
        mock_db = MagicMock()

        with patch("backend.utils.photo.get_child_for_processing", return_value=None):
            with pytest.raises(ConsentGateException):
                process_incoming_photo(
                    raw_bytes=garbage_bytes,
                    child_id=uuid.uuid4(),
                    center_id=uuid.uuid4(),
                    db=mock_db,
                    environment="production",
                )


class TestProcessIncomingPhotoValidation:
    """File type and size validation."""

    def test_rejects_file_over_10mb(self):
        """Files larger than 10MB must be rejected with ValueError."""

        # 11MB of fake data
        big_bytes = b"x" * (11 * 1024 * 1024)
        mock_db = MagicMock()

        with patch("backend.utils.photo.get_child_for_processing", return_value=MagicMock()):
            with pytest.raises(ValueError, match="10MB"):
                process_incoming_photo(
                    raw_bytes=big_bytes,
                    child_id=uuid.uuid4(),
                    center_id=uuid.uuid4(),
                    db=mock_db,
                    environment="development",
                )

    def test_rejects_invalid_file_type(self):
        """Non-image files must be rejected with ValueError."""

        # Fake PDF header
        pdf_bytes = b"%PDF-1.4 fake content"
        mock_db = MagicMock()

        with patch("backend.utils.photo.get_child_for_processing", return_value=MagicMock()):
            with pytest.raises(ValueError, match="(?i)format|type|unsupported"):
                process_incoming_photo(
                    raw_bytes=pdf_bytes,
                    child_id=uuid.uuid4(),
                    center_id=uuid.uuid4(),
                    db=mock_db,
                    environment="development",
                )


class TestS3KeyFormat:
    """S3 key must contain no PII."""

    def test_s3_key_contains_no_child_name(self):
        """S3 key must use UUID format only — no child name, no parent name."""

        child_id = uuid.uuid4()
        center_id = uuid.uuid4()

        key = build_photo_s3_key(center_id=center_id, child_id=child_id)

        # Key must contain the UUIDs but not any name
        assert str(child_id) in key
        assert str(center_id) in key

        # Key must start with the expected prefix
        assert key.startswith("photos/")
        assert key.endswith(".jpg")

    def test_s3_key_format_is_correct(self):
        """S3 key must be: photos/{center_id}/{child_id}/{date}/{uuid}.jpg"""

        child_id = uuid.uuid4()
        center_id = uuid.uuid4()

        key = build_photo_s3_key(center_id=center_id, child_id=child_id)

        # photos/{uuid}/{uuid}/YYYY-MM-DD/{uuid}.jpg
        pattern = r"^photos/[0-9a-f-]{36}/[0-9a-f-]{36}/\d{4}-\d{2}-\d{2}/[0-9a-f-]{36}\.jpg$"
        assert re.match(pattern, key), f"S3 key format invalid: {key}"
