"""Serializer fields that exist purely to match the API contract."""

import datetime as dt

from django.utils import timezone
from rest_framework import serializers


class NaiveUTCDateTimeField(serializers.DateTimeField):
    """Render as naive UTC with six fraction digits: 2026-08-23T10:48:52.245000.

    DRF's ISO-8601 default appends a ``Z``/offset for aware datetimes, and plain
    ``isoformat()`` drops the fraction entirely when microseconds happen to be 0
    - either one breaks a client parsing a fixed-width format.
    """

    def to_representation(self, value):
        if value is None:
            return None
        if timezone.is_aware(value):
            value = timezone.make_naive(value, dt.timezone.utc)
        return value.isoformat(timespec="microseconds")
