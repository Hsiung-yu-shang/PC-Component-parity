from pathlib import Path
from django.conf import settings
from django.core.checks import Error, register
from .sources import SOURCES


@register()
def source_configuration(app_configs, **kwargs):
    errors = []
    if set(settings.SYNC_SOURCES) - SOURCES.keys():
        errors.append(Error('SYNC_SOURCES 含不支援的來源。', id='core.E001'))
    if not 1 <= settings.SYNC_MAX_PAGES <= 5:
        errors.append(Error('SYNC_MAX_PAGES 必須介於 1 到 5。', id='core.E002'))
    if len(settings.PCHOME_KEYWORDS) > 50:
        errors.append(Error('PCHOME_KEYWORDS 最多 50 個關鍵字。', id='core.E003'))
    if settings.DB_SSL_CA and not Path(settings.DB_SSL_CA).is_file():
        errors.append(Error('DB_SSL_CA 檔案不存在。', id='core.E004'))
    return errors
