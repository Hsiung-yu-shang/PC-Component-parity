#!/bin/bash

# 以這個腳本檔案的位置為基準，自動推算出專案根目錄，
# 不用再手動寫死使用者帳號路徑（例如 /home/bearxiong/...），
# 換一台機器或換帳號 clone 都能直接用。
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_ROOT/forge_backend_server"
LOG_FILE="$PROJECT_ROOT/logs/crawler.log"

cd "$BACKEND_DIR"

# 啟動虛擬環境
source "$PROJECT_ROOT/venv/bin/activate"

echo "----------------------------------------" >> "$LOG_FILE"
echo "[$(date)] Job Started" >> "$LOG_FILE"

# 改用 Django management command，跟手動同步 API 走同一套邏輯（core/services.py），
# 不用再各自維護一份爬蟲寫入邏輯。
python3 manage.py sync_products >> "$LOG_FILE" 2>&1

echo "[$(date)] Job Finished" >> "$LOG_FILE"
echo "----------------------------------------" >> "$LOG_FILE"
