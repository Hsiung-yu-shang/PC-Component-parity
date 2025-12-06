#!/bin/bash

# 設定專案路徑
PROJECT_ROOT="/home/bearxiong/pc_crawler_project"
LOG_FILE="$PROJECT_ROOT/logs/crawler.log"

# 進入 src 目錄 (讓 Python 能正確 import pchome_core)
cd "$PROJECT_ROOT/src"

# 啟動虛擬環境
source "$PROJECT_ROOT/venv/bin/activate"

# 執行爬蟲並記錄 Log
echo "----------------------------------------" >> "$LOG_FILE"
echo "[$(date)] Job Started" >> "$LOG_FILE"

# 2>&1 代表將錯誤訊息也寫入 log
python3 batch_job.py >> "$LOG_FILE" 2>&1

echo "[$(date)] Job Finished" >> "$LOG_FILE"
echo "----------------------------------------" >> "$LOG_FILE"
