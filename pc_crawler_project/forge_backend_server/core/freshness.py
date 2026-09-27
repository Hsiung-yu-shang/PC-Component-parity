from datetime import timedelta
from django.conf import settings
from django.utils import timezone


def is_stale(updated):
    return updated is None or updated < timezone.now() - timedelta(hours=settings.PRICE_STALE_HOURS)
