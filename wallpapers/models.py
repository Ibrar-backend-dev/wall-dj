"""Data model behind the three wallpaper feeds.

Everything the API exposes is derived here rather than in the serializer, so a
row created from the admin, a shell or a future import all look identical.
"""

import os
import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from .validators import validate_media_extension, validate_thumbnail_extension


class MediaType(models.TextChoices):
    """Lowercase, exactly as the client parses it."""

    IMAGE = "image", "Image"
    GIF = "gif", "GIF"
    VIDEO = "video", "Video"


# Extension -> media_type. Anything unlisted is rejected by the validator first.
_MEDIA_TYPE_BY_EXTENSION = {
    "gif": MediaType.GIF,
    "mp4": MediaType.VIDEO,
    "jpg": MediaType.IMAGE,
    "jpeg": MediaType.IMAGE,
    "png": MediaType.IMAGE,
    "webp": MediaType.IMAGE,
}


def media_type_for(filename: str) -> str:
    extension = os.path.splitext(filename)[1].lstrip(".").lower()
    return _MEDIA_TYPE_BY_EXTENSION.get(extension, MediaType.IMAGE)


def title_from_filename(filename: str) -> str:
    """"beach sunset.jpg" -> "beach sunset".

    The extension is dropped because the same row already serves
    ``original_filename`` verbatim; keeping it would make the two fields
    identical in every payload. Clipped to the column width - SQLite would
    accept an over-long title silently where PostgreSQL raises.
    """
    stem = os.path.splitext(os.path.basename(filename or ""))[0]
    return stem[:150]


def wallpaper_upload_path(instance: "Wallpaper", filename: str) -> str:
    """wallpaper/<category-slug>/assets/<YYYY>/<MM>/<uuid4hex>.<ext>

    The stored name is random, so re-uploading the same file never collides and
    the original name is kept separately in ``original_filename``.
    """
    extension = os.path.splitext(filename)[1].lower()
    category_slug = getattr(instance.category, "slug", None) or "uncategorized"
    now = timezone.now()
    return (
        f"wallpaper/{category_slug}/assets/"
        f"{now:%Y}/{now:%m}/{uuid.uuid4().hex}{extension}"
    )


def thumbnail_upload_path(instance: "Wallpaper", filename: str) -> str:
    """The same layout as the asset, under ``thumbs/`` instead of ``assets/``."""
    extension = os.path.splitext(filename)[1].lower()
    category_slug = getattr(instance.category, "slug", None) or "uncategorized"
    now = timezone.now()
    return (
        f"wallpaper/{category_slug}/thumbs/"
        f"{now:%Y}/{now:%m}/{uuid.uuid4().hex}{extension}"
    )


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(
        max_length=120,
        unique=True,
        blank=True,
        help_text="Used in the media path. Left blank, it is built from the name.",
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Shown in the app. Served as null when left blank.",
    )
    position = models.PositiveIntegerField(
        default=0,
        db_index=True,
        help_text="Sort order in the feed; lower sorts first.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Unticked, the category disappears from the API.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("position", "name")
        verbose_name_plural = "categories"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:120]
        # An empty description is stored as NULL, so the API never has to
        # choose between "" and null.
        if not self.description:
            self.description = None
        super().save(*args, **kwargs)


class Wallpaper(models.Model):
    category = models.ForeignKey(
        Category,
        related_name="wallpapers",
        on_delete=models.PROTECT,
    )
    title = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        help_text=(
            "Set from the filename on upload. Clear it to serve null - "
            "the API never derives a title of its own."
        ),
    )
    file = models.FileField(
        upload_to=wallpaper_upload_path,
        validators=[validate_media_extension],
        help_text="jpeg, png, webp, gif or mp4.",
    )
    thumbnail = models.FileField(
        upload_to=thumbnail_upload_path,
        validators=[validate_thumbnail_extension],
        blank=True,
        null=True,
        help_text=(
            "Videos only, and entirely optional - the poster frame the app shows "
            "before playback. jpeg, png or webp. Served as thumbnail_path, null "
            "when unset."
        ),
    )
    media_type = models.CharField(
        max_length=10,
        choices=MediaType.choices,
        default=MediaType.IMAGE,
        editable=False,
        db_index=True,
    )
    original_filename = models.CharField(max_length=255, blank=True, null=True, editable=False)
    is_premium = models.BooleanField(default=False)
    priority = models.IntegerField(
        default=0,
        db_index=True,
        help_text="Higher sorts first, ahead of newer items.",
    )
    is_published = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Unticked, the item disappears from the API and from artwork_count.",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # "priority first then newest"; id breaks ties so paging stays stable.
        ordering = ("-priority", "-created_at", "-id")
        indexes = [
            models.Index(
                fields=["is_published", "-priority", "-created_at"],
                name="wp_feed_idx",
            ),
            models.Index(fields=["category", "is_published"], name="wp_category_idx"),
        ]

    def __str__(self) -> str:
        return self.title or self.original_filename or f"Wallpaper #{self.pk}"

    def clean(self):
        """Only a video may carry a thumbnail.

        An image or a gif already renders from ``file_path``, so a second
        image there is dead weight the API would have to serve. Derived from
        the file rather than ``self.media_type``, because media_type is only
        recomputed in save() - on a change form the field still holds the old
        value while the new file is sitting in front of us.
        """
        super().clean()
        if self.thumbnail and self.file and media_type_for(self.file.name) != MediaType.VIDEO:
            raise ValidationError(
                {"thumbnail": "Only videos take a thumbnail - this item is not a video."}
            )

    def save(self, *args, **kwargs):
        if self.file:
            # _committed is False only while a freshly assigned upload is still
            # under its client-side name, which is the one worth keeping.
            if not self.file._committed:
                self.original_filename = os.path.basename(self.file.name)[:255]
            self.media_type = media_type_for(self.file.name)
        if not self.title:
            self.title = None
        super().save(*args, **kwargs)
