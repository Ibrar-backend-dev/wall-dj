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

## Deploying to Railway

`railway.json` builds with Nixpacks, runs `collectstatic` at build time, then starts
`migrate` + gunicorn. The health check points at `/api/v1/wallpapers/categories`.

Railway injects `RAILWAY_PUBLIC_DOMAIN` and `PORT` - do not set those yourself. The
domain and Railway's `healthcheck.railway.app` host are appended to `ALLOWED_HOSTS`
automatically, and the domain is added to `CSRF_TRUSTED_ORIGINS`, so a deploy works
before the final domain is known.

### Variables to set on the service

| Variable | Value |
|---|---|
| `SECRET_KEY` | fresh random string, never the local one |
| `DEBUG` | `False` |
| `DATABASE_URL` | `${{ Postgres.DATABASE_URL }}` - a reference, not a pasted literal |
| `USE_LOCAL_MEDIA` | `False` |
| `B2_ENDPOINT` | e.g. `https://s3.us-west-004.backblazeb2.com` |
| `B2_REGION` | e.g. `us-west-004` |
| `B2_KEY_ID` / `B2_APP_KEY` / `B2_BUCKET` | from the B2 console; bucket must be public |
| `ALLOWED_HOSTS` | only if you add a custom domain |
| `CSRF_TRUSTED_ORIGINS` | only for a custom domain, with scheme: `https://example.com` |

**`USE_LOCAL_MEDIA` must be `False` in production.** Railway's filesystem is ephemeral,
so anything uploaded through the admin in local-media mode disappears on the next deploy
and every `file_path` 404s.

Two hardening settings stay opt-in because both can bite on first deploy:
`SECURE_SSL_REDIRECT` (Railway's health check can fail on the 301) and
`SECURE_HSTS_SECONDS` (irreversible for its max-age). Turn them on once a custom domain
is settled. Secure session and CSRF cookies are already on whenever `DEBUG` is `False`.

### Steps

```bash
railway init                 # or connect the repo on railway.app
railway add --database postgres
# set the variables above under Service -> Variables
railway up
railway run python manage.py createsuperuser
```

Then open `https://<your-domain>/admin/` to add categories and upload files.

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
