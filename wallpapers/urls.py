from django.urls import re_path

from .views import CategoryListView, WallpaperListView

# The collection calls these without a trailing slash; `/?` accepts either so a
# stray slash from a client is not a 404.
urlpatterns = [
    # Declared first so the literal path always wins.
    re_path(r"^wallpapers/categories/?$", CategoryListView.as_view(), name="wallpaper-categories"),
    re_path(r"^wallpapers/?$", WallpaperListView.as_view(), name="wallpaper-list"),
]
