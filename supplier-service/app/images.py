"""Supplier photos: checked, shrunk and stored as small WebP files.

Every image is decoded and re-encoded rather than stored as uploaded. That
proves the bytes really are an image whatever the file name or content type
claimed, drops metadata such as a phone's GPS position, and keeps each card
image around 50-150KB instead of the several MB a camera produces.

Storage is behind ImageStore so the local folder used in development can be
replaced by S3 when the service is deployed; the database only ever holds the
returned URL.
"""

import io
import mimetypes
import os
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_EDGE = 800
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}

# Refuse images that are small on disk but enormous once decoded.
Image.MAX_IMAGE_PIXELS = 40_000_000

# Slim container images ship without /etc/mime.types, so without this the
# stored files are served as text/plain.
mimetypes.add_type("image/webp", ".webp")


# Supplier cards show photos at this shape, so uploads are stored at it too.
CARD_RATIO = 16 / 9


class InvalidImageError(Exception):
    """The upload is not an image this service accepts."""


def crop_to_card(image: Image.Image, focus: float) -> Image.Image:
    """The CARD_RATIO part of the image at `focus` along the axis with spare room.

    `focus` runs from 0 (top, or left for a very wide image) to 1 (bottom, or
    right): the fraction of the spare room left above the kept part. That is
    the arithmetic CSS object-position uses with a percentage, which is what
    lets the admin form preview the crop exactly.
    """
    width, height = image.size
    if width / height < CARD_RATIO:
        kept = round(width / CARD_RATIO)
        top = round((height - kept) * focus)
        return image.crop((0, top, width, top + kept))
    kept = round(height * CARD_RATIO)
    left = round((width - kept) * focus)
    return image.crop((left, 0, left + kept, height))


def process_image(data: bytes, focus: float | None = None) -> bytes:
    """Validate an uploaded image and return it as a WebP of at most MAX_EDGE px.

    With `focus`, the image is first cropped to the card's shape at that
    position; without it, the whole image is kept.
    """
    if len(data) > MAX_UPLOAD_BYTES:
        raise InvalidImageError("Image must be 5MB or smaller.")
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in ALLOWED_FORMATS:
                raise InvalidImageError("Upload a JPEG, PNG or WebP image.")
            image.load()
            # Phones store rotation as metadata; apply it before discarding it.
            image = ImageOps.exif_transpose(image)
            image = image.convert("RGBA" if image.mode in ("RGBA", "LA", "P") else "RGB")
            if focus is not None:
                image = crop_to_card(image, focus)
            image.thumbnail((MAX_EDGE, MAX_EDGE))
            output = io.BytesIO()
            image.save(output, format="WEBP", quality=80, method=6)
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as error:
        raise InvalidImageError("Upload a JPEG, PNG or WebP image.") from error
    return output.getvalue()


class LocalImageStore:
    """Images in a folder, served by this service at URL_PREFIX.

    For development and Docker Compose, where the folder is a named volume so
    uploads survive container rebuilds.
    """

    URL_PREFIX = "/api/v1/supplier-images"

    def __init__(self, directory: Path):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def save(self, data: bytes) -> str:
        # The service picks the name, so an uploader can never choose a path.
        name = f"{uuid4().hex}.webp"
        (self.directory / name).write_bytes(data)
        return f"{self.URL_PREFIX}/{name}"


def create_image_store() -> LocalImageStore:
    directory = os.getenv("SUPPLIER_IMAGE_DIR") or str(
        Path(__file__).resolve().parents[1] / "uploads"
    )
    return LocalImageStore(Path(directory))
