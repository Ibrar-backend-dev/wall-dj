"""Upload rules for wallpaper media."""

from django.core.validators import FileExtensionValidator

# Per the API contract: jpeg, png, webp, gif and mp4.
ALLOWED_EXTENSIONS = ["jpg", "jpeg", "png", "webp", "gif", "mp4"]

validate_media_extension = FileExtensionValidator(allowed_extensions=ALLOWED_EXTENSIONS)

# A thumbnail stands in for a video in a grid, so it is a still image - no mp4,
# and no gif either, since an animated poster frame defeats the point.
ALLOWED_THUMBNAIL_EXTENSIONS = ["jpg", "jpeg", "png", "webp"]

validate_thumbnail_extension = FileExtensionValidator(
    allowed_extensions=ALLOWED_THUMBNAIL_EXTENSIONS
)
