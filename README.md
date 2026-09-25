# 電腦零件比價網

Django API 與 Vue 前端，定期同步 PChome 和原價屋的電腦零件價格。商品保留各來源的 ID、價格歷史、分類與規格，列表可依來源和分類篩選。

## 目前部署與搬遷

現行正式站是分離的 Web、API 與資料庫 VM，公開入口經 Cloudflare Tunnel。新的 `deploy/lxc-install.sh` 可把前端、API 和同步排程放進同一台 **Debian 12 或 Ubuntu 24.04 systemd LXC**，繼續連線既有 MySQL 8 資料庫。資料庫不搬移，舊 PChome 商品與歷史價格會保留；遷移新增 `source` 和 `product_url` 欄位。

部署前在 LXC 建立 `/root/pcpart.env`，填入 `SECRET_KEY`、`DB_HOST`、`DB_NAME`、`DB_USER`、`DB_PASSWORD`。例如在 root shell 下載範本，再編輯：

```bash
curl -fsSLo /root/pcpart.env https://raw.githubusercontent.com/Hsiung-yu-shang/PC-Component-parity/codex/lxc-dual-source/pc_crawler_project/forge_backend_server/.env.example
chmod 600 /root/pcpart.env
nano /root/pcpart.env
```

若沒有 `nano`，先執行 `apt-get install -y nano`。`DB_HOST` 可填既有資料庫的私網位址；資料庫須允許新 LXC 的 IP 連線。需要使用網頁上的管理員更新按鈕時，再設定隨機產生的 `SYNC_API_TOKEN`。先備份既有 MySQL 資料庫。不要將 `.env` 提交到 Git。

可在 LXC 執行 `python3 -c 'import secrets; print(secrets.token_urlsafe(48))'` 產生新的 `SECRET_KEY`。舊版程式曾把資料庫密碼與 Django 密鑰寫入程式碼；切換時應輪替兩者。

在全新 Debian／Ubuntu LXC 的 root shell，先安裝下載工具，再部署 `codex/lxc-dual-source` 測試分支：

```bash
apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl && curl -fsSLo /tmp/pcpart-install.sh https://raw.githubusercontent.com/Hsiung-yu-shang/PC-Component-parity/codex/lxc-dual-source/deploy/lxc-install.sh && PCPART_REF=codex/lxc-dual-source bash /tmp/pcpart-install.sh /root/pcpart.env
```

測試完成並合併到 GitHub `main` 後，改用正式分支安裝或更新：

```bash
apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl && curl -fsSLo /tmp/pcpart-install.sh https://raw.githubusercontent.com/Hsiung-yu-shang/PC-Component-parity/main/deploy/lxc-install.sh && bash /tmp/pcpart-install.sh /root/pcpart.env
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

## 商品詳情跨通路比價

商品詳情會自動比對另一來源已收錄、仍上架且有價格的商品，無論從 PChome 或原價屋進入都能使用。標示「原價屋 · 實體通路」和「PChome · 線上購物」，列出各通路價格、價差及最後更新日期。結果依型號及可辨識的容量、版本等規格保守配對；缺少完整料號、散裝／盒裝差異、搭購或無法確認的資料不會硬配對。GPU 不會僅憑 RTX 晶片名稱配對不同品牌或散熱版本。未找到配對不代表該通路没有販售。

比價只查本機資料庫，候選資料快取五分鐘，不會因訪客開頁面對原價屋發出請求。原價屋名稱中的 `{}`／`｛｝` 會立即從 API 顯示移除，括號內的型號文字保留；同步更新名称時仍沿用舊 ID，保留價格歷史。

## 同步頻率及原價屋存取

- 原價屋估價頁最多每六小時一個請求；robots.txt 最多每天檢查一次並遵守其規則。讀取新的 robots 後也會間隔請求。
- 手動按鈕、systemd 排程和 CLI 共用檔案鎖；整體同步至少間隔 15 分鐘。
- 403／429 至少等待 24 小時，遵守更長的 Retry-After；連續失敗指數退避至最長 72 小時（伺服器要求更長則依伺服器）。不重試轟炸、繞驗證或切換 IP。
- 異常頁面、樣本過少及來源錯誤保留原有商品及價格。管理員介面會顯示沿用價格或來源暫停。
- 生產狀態目錄為 `/var/lib/pcpart`。不要刪除冷卻檔案或為不同同步程序設定不同 `SYNC_STATE_DIR`。這些措施降低負載與封鎖風險，不能保證原價屋不會封鎖。

## 更新此測試分枝

在 LXC 的 root shell 重新下載安裝腳本後執行；使用既有 `/root/pcpart.env`，不需重新填密碼。此版本沒有新增資料庫遷移。

```bash
curl -fsSLo /tmp/pcpart-install.sh https://raw.githubusercontent.com/Hsiung-yu-shang/PC-Component-parity/codex/lxc-dual-source/deploy/lxc-install.sh && PCPART_REF=codex/lxc-dual-source bash /tmp/pcpart-install.sh /root/pcpart.env
```

重新載入 `http://10.10.0.249:8080/`，分別從兩個來源進入相同型號商品，確認比價與實體通路標籤。清除 `{}` 不需要先跑爬蟲。正式網域前請確認 Cloudflare HTTPS；安全 Cookie 預設啟用，直接透過 HTTP IP 測試商品頁不受影響，Django admin 登入應使用 HTTPS。

安全檢測結果與適用範圍見 [SECURITY_REVIEW.md](SECURITY_REVIEW.md)。
