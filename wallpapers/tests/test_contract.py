"""The API contract, asserted literally.

The client parses a fixed shape, so these tests care about key *order*, null
semantics and the exact datetime format - not just "the right data came back".
"""

import json
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from wallpapers.models import Category, Wallpaper

# Smallest valid 1x1 PNG; the other bodies only need a plausible header.
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c6360000002000100ffff03000006000557bfabd4000000"
    "0049454e44ae426082"
)
MP4 = b"\x00\x00\x00\x18ftypmp42"
GIF = b"GIF89a"

HOST = "192.168.18.8:8000"

CATEGORY_KEYS = ["id", "name", "description", "position", "artwork_count"]
WALLPAPER_KEYS = [
    "media_type",
    "is_premium",
    "title",
    "id",
    "category_id",
    "original_filename",
    "file_path",
    "created_at",
]
META_KEYS = ["page", "page_size", "total", "has_next"]

_TEMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=_TEMP_MEDIA, USE_LOCAL_MEDIA=True)
class FeedContractTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.anime = Category.objects.create(
            name="Anime", description="Anime wallpapers wonderful styles .", position=0
        )
        cls.nature = Category.objects.create(name="Nature", position=1)  # blank description
        cls.hidden = Category.objects.create(name="Hidden", position=2, is_active=False)

        # Named, premium, png.
        cls.w_png = Wallpaper.objects.create(
            category=cls.anime,
            title="wallpaper",
            is_premium=True,
            file=SimpleUploadedFile("my shot.png", PNG, content_type="image/png"),
        )
        # Untitled, top priority, video.
        cls.w_mp4 = Wallpaper.objects.create(
            category=cls.anime,
            priority=5,
            file=SimpleUploadedFile("clip.mp4", MP4, content_type="video/mp4"),
        )
        cls.w_gif = Wallpaper.objects.create(
            category=cls.anime,
            title="loop",
            file=SimpleUploadedFile("anim.gif", GIF, content_type="image/gif"),
        )
        # Unpublished: must not surface anywhere, including artwork_count.
        cls.w_draft = Wallpaper.objects.create(
            category=cls.nature,
            title="unpublished",
            is_published=False,
            file=SimpleUploadedFile("x.png", PNG, content_type="image/png"),
        )

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(_TEMP_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def get(self, path):
        response = self.client.get(path, HTTP_HOST=HOST)
        return response, json.loads(response.content)

    # --- 1. categories ---------------------------------------------------

    def test_category_feed_shape_and_key_order(self):
        response, body = self.get("/api/v1/wallpapers/categories")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(body), ["data", "meta"])
        self.assertEqual(list(body["data"][0]), CATEGORY_KEYS)
        self.assertEqual(list(body["meta"]), META_KEYS)
        self.assertEqual(body["meta"], {"page": 1, "page_size": 20, "total": 2, "has_next": False})

    def test_categories_are_active_only_and_ordered_by_id(self):
        _, body = self.get("/api/v1/wallpapers/categories")
        self.assertEqual([c["id"] for c in body["data"]], [self.anime.id, self.nature.id])

    def test_artwork_count_counts_published_items_only(self):
        _, body = self.get("/api/v1/wallpapers/categories")
        self.assertEqual(body["data"][0]["artwork_count"], 3)
        self.assertEqual(body["data"][1]["artwork_count"], 0)  # holds only an unpublished item

    def test_blank_description_is_null(self):
        _, body = self.get("/api/v1/wallpapers/categories")
        self.assertIsNone(body["data"][1]["description"])

    def test_categories_carry_no_thumbnail(self):
        _, body = self.get("/api/v1/wallpapers/categories")
        self.assertEqual(set(body["data"][0]), set(CATEGORY_KEYS))

    # --- 2. all wallpapers -----------------------------------------------

    def test_wallpaper_feed_shape_and_key_order(self):
        response, body = self.get("/api/v1/wallpapers")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(body), ["data", "meta"])
        self.assertEqual(list(body["data"][0]), WALLPAPER_KEYS)
        self.assertEqual(list(body["meta"]), META_KEYS)

    def test_color_code_is_not_served(self):
        _, body = self.get("/api/v1/wallpapers")
        self.assertNotIn("color_code", body["data"][0])

    def test_unpublished_items_are_excluded(self):
        _, body = self.get("/api/v1/wallpapers")
        self.assertEqual(body["meta"]["total"], 3)

    def test_ordering_is_priority_first_then_newest(self):
        _, body = self.get("/api/v1/wallpapers")
        self.assertEqual(
            [row["id"] for row in body["data"]],
            [self.w_mp4.id, self.w_gif.id, self.w_png.id],
        )

    def test_untitled_item_serves_null_not_the_filename(self):
        _, body = self.get("/api/v1/wallpapers")
        row = next(r for r in body["data"] if r["id"] == self.w_mp4.id)
        self.assertIsNone(row["title"])
        self.assertEqual(row["original_filename"], "clip.mp4")

    def test_original_filename_survives_the_storage_rename(self):
        _, body = self.get("/api/v1/wallpapers")
        row = next(r for r in body["data"] if r["id"] == self.w_png.id)
        self.assertEqual(row["original_filename"], "my shot.png")

    def test_media_type_is_derived_and_lowercase(self):
        _, body = self.get("/api/v1/wallpapers")
        by_id = {r["id"]: r["media_type"] for r in body["data"]}
        self.assertEqual(by_id[self.w_mp4.id], "video")
        self.assertEqual(by_id[self.w_gif.id], "gif")
        self.assertEqual(by_id[self.w_png.id], "image")

    def test_file_path_is_absolute_and_follows_the_upload_layout(self):
        _, body = self.get("/api/v1/wallpapers")
        row = next(r for r in body["data"] if r["id"] == self.w_png.id)
        self.assertRegex(
            row["file_path"],
            r"^http://192\.168\.18\.8:8000/media/wallpaper/anime/assets/"
            r"\d{4}/\d{2}/[0-9a-f]{32}\.png$",
        )

    def test_created_at_is_naive_utc_with_six_fraction_digits(self):
        _, body = self.get("/api/v1/wallpapers")
        for row in body["data"]:
            self.assertRegex(
                row["created_at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}$"
            )

    # --- 3. wallpapers by category ---------------------------------------

    def test_by_category_serves_an_identical_row_shape(self):
        _, unfiltered = self.get("/api/v1/wallpapers")
        response, body = self.get(f"/api/v1/wallpapers?category_id={self.anime.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(body["data"][0]), list(unfiltered["data"][0]))
        self.assertEqual(body["meta"]["total"], 3)

    def test_category_holding_only_unpublished_items_is_empty(self):
        _, body = self.get(f"/api/v1/wallpapers?category_id={self.nature.id}")
        self.assertEqual(body["data"], [])

    def test_unknown_category_id_is_an_empty_list_not_an_error(self):
        response, body = self.get("/api/v1/wallpapers?category_id=999999")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["data"], [])

    def test_non_numeric_category_id_is_a_400(self):
        response, body = self.get("/api/v1/wallpapers?category_id=abc")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(list(body), ["detail"])

    # --- paging ----------------------------------------------------------

    def test_page_size_over_the_cap_is_a_400_not_a_clamp(self):
        for path in ("/api/v1/wallpapers", "/api/v1/wallpapers/categories"):
            with self.subTest(path=path):
                response, _ = self.get(f"{path}?page_size=101")
                self.assertEqual(response.status_code, 400)

    def test_page_size_at_the_cap_is_accepted(self):
        response, _ = self.get("/api/v1/wallpapers?page_size=100")
        self.assertEqual(response.status_code, 200)

    def test_page_past_the_end_is_an_empty_list_not_a_404(self):
        response, body = self.get("/api/v1/wallpapers?page=9999")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["data"], [])
        self.assertFalse(body["meta"]["has_next"])

    def test_has_next_walks_the_feed(self):
        _, first = self.get("/api/v1/wallpapers?page_size=2")
        self.assertEqual(first["meta"], {"page": 1, "page_size": 2, "total": 3, "has_next": True})
        _, last = self.get("/api/v1/wallpapers?page=2&page_size=2")
        self.assertEqual(last["meta"], {"page": 2, "page_size": 2, "total": 3, "has_next": False})

    def test_non_positive_or_non_numeric_paging_is_a_400(self):
        for query in ("page=0", "page=-1", "page=abc", "page_size=0", "page_size=abc"):
            with self.subTest(query=query):
                response, _ = self.get(f"/api/v1/wallpapers?{query}")
                self.assertEqual(response.status_code, 400)
