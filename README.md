# 電腦零件比價網

Django API 與 Vue 前端，定期同步 PChome 和原價屋的電腦零件價格。商品保留各來源的 ID、價格歷史、分類與規格，列表可依來源和分類篩選。

## 目前部署與搬遷

現行正式站是分離的 Web、API 與資料庫 VM，公開入口經 Cloudflare Tunnel。新的 `deploy/lxc-install.sh` 可把前端、API 和同步排程放進同一台 **Debian 12 或 Ubuntu 24.04 systemd LXC**，繼續連線既有 MySQL 8 資料庫。資料庫不搬移，舊 PChome 商品與歷史價格會保留；遷移新增 `source` 和 `product_url` 欄位。

部署前在 LXC 建立 `/root/pcpart.env`（可複製 `pc_crawler_project/forge_backend_server/.env.example`），填入 `SECRET_KEY`、`DB_HOST`、`DB_NAME`、`DB_USER`、`DB_PASSWORD`。需要使用網頁上的管理員更新按鈕時，再設定隨機產生的 `SYNC_API_TOKEN`。`DB_HOST` 使用從 LXC 可達的資料庫私網位址；資料庫須允許該 LXC 使用者連線。先備份既有 MySQL 資料庫。不要將 `.env` 提交到 Git。

可在 LXC 執行 `python3 -c 'import secrets; print(secrets.token_urlsafe(48))'` 產生新的 `SECRET_KEY`。舊版程式曾把資料庫密碼與 Django 密鑰寫入程式碼；切換時應輪替兩者。

先推送 `codex/lxc-dual-source` 測試分支，在 LXC 的 root shell 以一行指令部署該分支：

```bash
curl -fsSLo /tmp/pcpart-install.sh https://raw.githubusercontent.com/Hsiung-yu-shang/PC-Component-parity/codex/lxc-dual-source/deploy/lxc-install.sh && PCPART_REF=codex/lxc-dual-source bash /tmp/pcpart-install.sh /root/pcpart.env
```

測試完成並合併到 GitHub `main` 後，改用正式分支安裝或更新：

```bash
curl -fsSLo /tmp/pcpart-install.sh https://raw.githubusercontent.com/Hsiung-yu-shang/PC-Component-parity/main/deploy/lxc-install.sh && bash /tmp/pcpart-install.sh /root/pcpart.env
```

腳本安裝 Python、Node.js、Nginx，執行 `migrate` 與前端建置，建立 Gunicorn API、每六小時同步兩來源的 systemd timer。Nginx 在 LXC 的 `8080` 提供網頁與同源 `/api/`。LXC 完成後，將 `pcpart.hsiungyusheng.me` 的 Tunnel origin 指向 `http://<LXC-IP>:8080`；可再將舊 API hostname 指向同台 `8080`，或保留舊 VM 至確認切換完成。新前端只使用同源 `/api/`。

```bash
systemctl status pcpart-api pcpart-sync.timer
sudo systemctl start pcpart-sync.service
journalctl -u pcpart-sync.service -n 100 --no-pager
curl http://127.0.0.1:8080/api/products/?source=coolpc
```

原價屋報價來自公開[線上估價頁](https://www.coolpc.com.tw/evaluate.php)，商品連結會回到該估價頁，並非單一商品結帳頁。原價屋是估價參考，最終售價與供貨以店家確認為準。網站標記來源，避免把估價當作 PChome 售價。網頁結構改動可能使解析失效；空結果及大量缺漏時同步不會整批下架原價屋資料。

## 本機開發

後端使用 `pc_crawler_project/forge_backend_server/requirements.txt`，設定範本同目錄 `.env.example`；執行 `python manage.py migrate`、`python manage.py runserver`。前端在 `pc-price-frontend` 執行 `npm ci`、`npm run dev`，Vite 會把 `/api` 代理到本機 `8000`。正式環境使用 Gunicorn 與 Nginx，不使用 Django 開發伺服器。
