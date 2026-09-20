"""The whole content-management surface: categories and uploads live here."""

from django.contrib import admin
from django.db.models import Count, Q
from django.utils.html import format_html

from .models import Category, MediaType, Wallpaper


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "position", "is_active", "artwork_count")
    list_editable = ("position", "is_active")
    list_display_links = ("name",)
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("position", "name")
    fields = ("name", "slug", "description", "position", "is_active")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(
                artwork_count=Count("wallpapers", filter=Q(wallpapers__is_published=True))
            )
        )

    @admin.display(description="Published items", ordering="artwork_count")
    def artwork_count(self, obj):
        return obj.artwork_count


@admin.register(Wallpaper)
class WallpaperAdmin(admin.ModelAdmin):
    list_display = (
        "preview",
        "display_title",
        "category",
        "media_type",
        "is_premium",
        "is_published",
        "priority",
        "created_at",
    )
    list_display_links = ("preview", "display_title")
    list_editable = ("is_premium", "is_published", "priority")
    list_filter = ("category", "media_type", "is_premium", "is_published")
    search_fields = ("title", "original_filename")
    list_select_related = ("category",)
    date_hierarchy = "created_at"
    readonly_fields = ("preview_large", "media_type", "original_filename", "file_path", "created_at")
    actions = ("publish", "unpublish", "mark_premium", "mark_free")
    fieldsets = (
        (None, {"fields": ("category", "title", "file", "preview_large")}),
        ("Placement", {"fields": ("priority", "is_premium", "is_published")}),
        (
            "Derived",
            {
                "fields": ("media_type", "original_filename", "file_path", "created_at"),
                "description": "Filled in automatically from the upload.",
            },
        ),
    )

    @admin.display(description="Title", ordering="title")
    def display_title(self, obj):
        return obj.title or "(untitled)"

    @admin.display(description="Preview")
    def preview(self, obj):
        return self._render_preview(obj, width=60)

    @admin.display(description="Preview")
    def preview_large(self, obj):
        return self._render_preview(obj, width=320)

    @admin.display(description="file_path")
    def file_path(self, obj):
        if not obj.file:
            return "-"
        return format_html('<a href="{0}" target="_blank">{0}</a>', obj.file.url)

    @staticmethod
    def _render_preview(obj, width):
        if not obj.file:
            return "-"
        if obj.media_type == MediaType.VIDEO:
            return format_html(
                '<video src="{}" width="{}" muted loop playsinline '
                'onmouseover="this.play()" onmouseout="this.pause()"></video>',
                obj.file.url,
                width,
            )
        return format_html(
            '<img src="{}" width="{}" style="border-radius:4px;object-fit:cover" />',
            obj.file.url,
            width,
        )

    @admin.action(description="Publish selected wallpapers")
    def publish(self, request, queryset):
        self.message_user(request, f"{queryset.update(is_published=True)} published.")

    @admin.action(description="Unpublish selected wallpapers")
    def unpublish(self, request, queryset):
        self.message_user(request, f"{queryset.update(is_published=False)} unpublished.")

    @admin.action(description="Mark selected as premium")
    def mark_premium(self, request, queryset):
        self.message_user(request, f"{queryset.update(is_premium=True)} marked premium.")

    @admin.action(description="Mark selected as free")
    def mark_free(self, request, queryset):
        self.message_user(request, f"{queryset.update(is_premium=False)} marked free.")


admin.site.site_header = "Wallpaper API admin"
admin.site.site_title = "Wallpaper API"
admin.site.index_title = "Content"
