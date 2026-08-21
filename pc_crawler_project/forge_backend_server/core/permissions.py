from django.conf import settings
from rest_framework.permissions import BasePermission


class HasSyncToken(BasePermission):
    """
    保護「手動同步」這種昂貴、會對外發送大量請求的 API。

    呼叫端必須在 Header 帶上：
        X-Sync-Token: <SYNC_API_TOKEN 的值>

    這個 token 存在 .env 的 SYNC_API_TOKEN，不會被 commit 進 git。
    這不是完整的使用者認證系統，只是一個輕量的「內部操作密鑰」，
    目的是避免任何訪客都能觸發耗時的爬蟲同步（DoS 風險 / 洗爆 PChome 的 IP）。
    """
    message = "缺少或錯誤的同步權杖 (X-Sync-Token)。"

    def has_permission(self, request, view):
        token = request.headers.get('X-Sync-Token', '')
        expected = getattr(settings, 'SYNC_API_TOKEN', '')
        # 沒有設定 SYNC_API_TOKEN 的話，一律拒絕，避免預設就開後門
        if not expected:
            return False
        return token == expected
