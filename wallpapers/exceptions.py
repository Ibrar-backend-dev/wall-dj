"""Uniform error body: {"detail": "..."} for every 4xx."""

from rest_framework.views import exception_handler


def _first_message(detail):
    if isinstance(detail, dict):
        return _first_message(next(iter(detail.values()), ""))
    if isinstance(detail, list):
        return _first_message(detail[0]) if detail else ""
    return str(detail)


def detail_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None and not (
        isinstance(response.data, dict) and set(response.data) == {"detail"}
    ):
        response.data = {"detail": _first_message(response.data)}
    return response
