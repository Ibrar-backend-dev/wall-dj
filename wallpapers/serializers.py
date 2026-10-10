"""Response rows.

Key order is part of the contract: DRF builds the row in ``Meta.fields`` order
and JSONRenderer preserves it, so these tuples must not be "tidied up" into
alphabetical or model order.
"""

from django.conf import settings
from rest_framework import serializers

from .fields import NaiveUTCDateTimeField
from .models import Category, Wallpaper


class CategorySerializer(serializers.ModelSerializer):
    # Comes from the queryset annotation in the view, not a per-row query.
    artwork_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = ("id", "name", "description", "position", "artwork_count")


class WallpaperSerializer(serializers.ModelSerializer):
    # Reads the FK column straight off the instance - no join.
    category_id = serializers.IntegerField(read_only=True)
    artwork = serializers.SerializerMethodField()
    created_at = NaiveUTCDateTimeField(read_only=True)
    thumbnail_path = serializers.SerializerMethodField()

    class Meta:
        model = Wallpaper
        fields = (
            "id",
            "category_id",
            "media_type",
            "is_premium",
            "title",
            "artwork",
            "created_at",
            "thumbnail_path",
        )

    def get_artwork(self, obj) -> str | None:
        return self._absolute(obj.file)

    def get_thumbnail_path(self, obj) -> str | None:
        """Null unless a video has been given one - never derived from the file."""
        return self._absolute(obj.thumbnail)

    def _absolute(self, filefield) -> str | None:
        """Always an absolute, directly loadable url.

        Under B2 the storage backend already returns one; the local-media
        fallback returns /media/... which we absolutize against the request.
        """
        if not filefield:
            return None
        url = filefield.url
        if settings.USE_LOCAL_MEDIA:
            request = self.context.get("request")
            if request is not None:
                return request.build_absolute_uri(url)
        return url
