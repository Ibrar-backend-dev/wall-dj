# Wallpaper API

Django + DRF + Postgres backend serving three public wallpaper feeds, with media on
Backblaze B2 and Django admin as the only content-management surface.

## Endpoints

All are public GETs under `/api/v1/`, JSON only.

| # | Endpoint | Notes |
|---|---|---|
| 1 | `GET /api/v1/wallpapers/categories` | Active categories, ordered `position` then `name` |
| 2 | `GET /api/v1/wallpapers` | Published items, priority first then newest |
| 3 | `GET /api/v1/wallpapers?category_id=N` | Same endpoint, one filter, identical row shape |

Every response is the same envelope:

```json
{ "data": [ ... ], "meta": { "page": 1, "page_size": 20, "total": 1, "has_next": false } }
```

### Category row

`id, name, description, position, artwork_count` — in that order. `description` is `null`
when blank; `artwork_count` counts published items only. Categories carry no thumbnail.

### Wallpaper row

`media_type, is_premium, title, id, category_id, original_filename, file_path, created_at`
— in that order, which is deliberate and not alphabetical.

- `file_path` is an **absolute** url. Load it directly; prefixing it with the base url
  gives a doubled address and a broken image. There is no thumbnail or preview url.
- `media_type` is lowercase `image`, `gif` or `video`, derived from the uploaded file.
- `title` is `null` for an unnamed item — it never falls back to the filename.
- `created_at` is naive UTC with microseconds, e.g. `2026-08-23T10:48:52.245000`.

### Query parameters

| Param | Default | Behaviour |
|---|---|---|
| `page` | 1 | 1-based. Past the end returns an empty list, not an error. |
| `page_size` | 20 | Max 100. Over the cap is a **400**, not a silent clamp. |
| `category_id` | — | Feed 3 only. Non-numeric is a 400; an unknown id returns an empty list. |

Errors come back as `{"detail": "..."}`.

## Setup

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt     # Windows; use .venv/bin/pip elsewhere

cp .env.example .env                              # then edit it

.venv/Scripts/python manage.py migrate
.venv/Scripts/python manage.py createsuperuser
.venv/Scripts/python manage.py runserver 0.0.0.0:8000
```

Add a category and upload files at `/admin/`, then hit the endpoints above.

## Storage

`USE_LOCAL_MEDIA=True` (the default) keeps files in `./media` and builds `file_path` from
the request host, so the API runs with no B2 credentials.

Set it to `False` and fill the `B2_*` values to switch to Backblaze B2, which is driven
through its S3-compatible API. The bucket must be **public**: responses carry unsigned,
cacheable urls straight to B2 (or to `B2_CDN_DOMAIN`, if a CDN sits in front of it).
Nothing else changes — uploads keep the same
`wallpaper/<category>/assets/<YYYY>/<MM>/<uuid>.<ext>` layout.

## Tests

`wallpapers/tests/test_contract.py` asserts the contract literally — key order, null
handling, the `created_at` format, ordering, and every 400 / empty-list edge case above.

```bash
.venv/Scripts/python manage.py test
```

It uses SQLite by default. To test against PostgreSQL instead, set `DATABASE_URL` to a
reachable PostgreSQL URL first. Media goes to a temp directory during the run; B2 is
never touched.
