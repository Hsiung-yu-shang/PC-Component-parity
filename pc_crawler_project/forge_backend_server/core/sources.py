"""Trusted source registry. Adding a source requires a reviewed adapter, never an arbitrary URL."""
from dataclasses import dataclass
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


@dataclass(frozen=True)
class Source:
    key: str
    label: str
    channel: str
    full_catalog: bool = False

    def spider(self):
        if self.key == 'pchome':
            from .crawler import PChomeSpider
            return PChomeSpider()
        if self.key == 'coolpc':
            from .coolpc import CoolPCSpider
            return CoolPCSpider()
        raise ImproperlyConfigured('來源缺少已審核的爬蟲。')


SOURCES = {
    'pchome': Source('pchome', 'PChome', '線上購物'),
    'coolpc': Source('coolpc', '原價屋', '實體通路', full_catalog=True),
}


def enabled_sources():
    values = tuple(dict.fromkeys(settings.SYNC_SOURCES))
    if set(values) - SOURCES.keys():
        raise ImproperlyConfigured('SYNC_SOURCES 含不支援的來源。')
    return values


def resolve_sources(requested=None):
    enabled = enabled_sources()
    if requested is None:
        return enabled
    if not isinstance(requested, (list, tuple)) or not requested:
        raise ValueError('sources 必須是非空來源清單。')
    if any(not isinstance(s, str) or s not in enabled for s in requested):
        raise ValueError('指定來源不存在或已停用同步。')
    return tuple(dict.fromkeys(requested))
