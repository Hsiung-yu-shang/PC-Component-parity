"""
[已棄用] 這支腳本的邏輯已經整合進 Django app 裡的
core/services.py + core/management/commands/sync_products.py。

請改用：
    cd pc_crawler_project/forge_backend_server
    python3 manage.py sync_products

排程腳本 scripts/run_crawler.sh 已經同步更新為呼叫上面這個指令。

保留這支檔案只是避免舊排程設定找不到檔案而直接報錯；
它本身不再包含爬蟲邏輯，執行下去只會印出提示訊息並結束。
"""
import sys

if __name__ == "__main__":
    print(
        "[batch_job.py] 這支腳本已棄用。\n"
        "請改執行： python3 manage.py sync_products\n"
        "（在 pc_crawler_project/forge_backend_server 目錄下執行）"
    )
    sys.exit(1)
