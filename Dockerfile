FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Baked into the image so the running container serves the admin's CSS.
RUN python manage.py collectstatic --noinput

# Shell form: $PORT is injected by Railway at runtime.
CMD python manage.py migrate --noinput && \
    gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 1 --timeout 60
