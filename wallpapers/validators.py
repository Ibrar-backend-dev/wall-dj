"""Upload rules for wallpaper media."""

from django.core.validators import FileExtensionValidator

# Per the API contract: jpeg, png, webp, gif and mp4.
ALLOWED_EXTENSIONS = ["jpg", "jpeg", "png", "webp", "gif", "mp4"]

validate_media_extension = FileExtensionValidator(allowed_extensions=ALLOWED_EXTENSIONS)
