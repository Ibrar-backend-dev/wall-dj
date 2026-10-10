"""Thumbnail generation for image wallpapers.

The target is a file roughly three times smaller than the original. Bytes, not
pixels - so the work is "shrink until it fits" rather than a fixed ratio: a
flat illustration compresses far harder than a photograph, and a fixed scale
would overshoot wildly on one and undershoot on the other.

Videos are not handled here. Pulling a poster frame out of an mp4 needs ffmpeg,
which is neither installed nor in the image, so a video's thumbnail stays a
manual upload in the admin.
"""

from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image

# How much smaller the thumbnail must be than the wallpaper it came from.
SIZE_DIVISOR = 3

# Tried largest first, so the result is the biggest version that still fits
# under the budget rather than the smallest one that happens to work.
_SCALES = (0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.15, 0.1)
_QUALITY = 82


def _encode(image, scale: int) -> bytes:
    width = max(1, round(image.width * scale))
    height = max(1, round(image.height * scale))
    buffer = BytesIO()
    # WebP carries alpha and beats both JPEG and PNG at this size, and the
    # thumbnail validator already accepts it.
    image.resize((width, height), Image.LANCZOS).save(
        buffer, format="WEBP", quality=_QUALITY, method=4
    )
    return buffer.getvalue()


def build_thumbnail(source, original_size: int, name: str = "thumb.webp"):
    """Return a ``ContentFile`` at most ``original_size // SIZE_DIVISOR`` bytes.

    ``source`` is left rewound, because the caller is about to hand the very
    same file object to storage - consuming the stream here without seeking
    back would write an empty wallpaper.
    """
    budget = max(1, original_size // SIZE_DIVISOR)

    try:
        source.seek(0)
        with Image.open(source) as image:
            image.load()
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGBA" if "A" in image.getbands() else "RGB")

            smallest = None
            for scale in _SCALES:
                encoded = _encode(image, scale)
                if len(encoded) <= budget:
                    return ContentFile(encoded, name=name)
                smallest = encoded
    except (OSError, ValueError, Image.DecompressionBombError):
        # A file Pillow cannot read is not worth failing an upload over - the
        # wallpaper still saves, just without a thumbnail.
        return None
    finally:
        source.seek(0)

    # Already tiny, or so noisy it will not compress: the smallest attempt is
    # still a smaller file to ship than the original.
    return ContentFile(smallest, name=name) if smallest else None
