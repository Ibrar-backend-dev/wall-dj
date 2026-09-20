"""The three public feeds.

Requests 2 and 3 of the collection are one view with one optional filter, so
both serve byte-identical row shapes.
"""

from django.db.models import Count, Q
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Category, Wallpaper
from .pagination import paginate
from .serializers import CategorySerializer, WallpaperSerializer


class FeedView(APIView):
    """Shared envelope: {"data": [...], "meta": {...}}, in that order."""

    serializer_class = None

    def get_queryset(self, request):
        raise NotImplementedError

    def get(self, request):
        items, meta = paginate(self.get_queryset(request), request)
        serializer = self.serializer_class(items, many=True, context={"request": request})
        return Response({"data": serializer.data, "meta": meta})


class CategoryListView(FeedView):
    """GET /api/v1/wallpapers/categories"""

    serializer_class = CategorySerializer

    def get_queryset(self, request):
        return (
            Category.objects.filter(is_active=True)
            .annotate(
                artwork_count=Count(
                    "wallpapers",
                    filter=Q(wallpapers__is_published=True),
                )
            )
            .order_by("id")
        )


class WallpaperListView(FeedView):
    """GET /api/v1/wallpapers  and  GET /api/v1/wallpapers?category_id=N"""

    serializer_class = WallpaperSerializer

    def get_queryset(self, request):
        queryset = Wallpaper.objects.filter(is_published=True)

        raw_category_id = request.query_params.get("category_id")
        if raw_category_id not in (None, ""):
            try:
                category_id = int(raw_category_id)
            except (TypeError, ValueError):
                raise ValidationError("category_id must be an integer.")
            # An id that matches nothing simply yields an empty feed, so there
            # is no existence check to make here.
            queryset = queryset.filter(category_id=category_id)

        return queryset
