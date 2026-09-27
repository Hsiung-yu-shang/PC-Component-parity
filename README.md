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

## 來源設定與擴充

以下欄位可加到既有 `/root/pcpart.env`，未填時沿用預設值；修改後重新執行安裝腳本，讓服務讀到新設定。

| 欄位 | 預設／用途 |
| --- | --- |
| `SYNC_SOURCES` | `pchome,coolpc`；可只填 `coolpc` 或 `pchome`。明確留空暫停全部同步，既有價格仍可查詢。 |
| `PCHOME_KEYWORDS` | 逗號分隔，例如 `AMD Ryzen 7,SSD 2TB,DDR5 32GB`；空白使用內建清單，最多 50 個。PChome 為取樣搜尋，並非完整商品目錄。 |
| `SYNC_MAX_PAGES` | `2`；每關鍵字 1–5 頁。 |
| `COOLPC_MIN_INTERVAL_SECONDS` | `21600`；可延長原價屋冷卻，不能縮短至六小時以下。 |
| `PRICE_STALE_HOURS` | `48`；超過最後確認時間即顯示舊價格提醒，最小 6 小時。 |
| `DB_SSL_CA` | 預設空白；填資料庫 CA 的絕對路徑後，要求 TLS 並驗證伺服器身分。 |

來源選單由 `/api/sources/` 提供；管理員更新只同步所選來源，全部則同步啟用的來源。停用同步不會刪除該來源的歷史商品。單一來源被擋／逾時時，另一來源仍可完成更新。PChome 請求至少間隔兩秒，403／429 至少退避 24 小時並保存在共用目錄。

新增第三個來源需新增經審核的爬蟲、在 `core/sources.py` 註冊、接上 `core/services.py` 的資料迭代方式，並更新前端 `storeUrl.js` 的 HTTPS 網域白名單及測試。商品 ID 必須避免與既有来源碰撞。不能只填任意 URL 就抓取，以免形成內網存取或惡意連結漏洞。

詳情只預覽最近 100 筆價格與評論；完整紀錄可透過 `/api/products/<id>/history/` 與 `/api/products/<id>/reviews/` 分頁讀取（每頁 20 筆）。已下架商品仍可讀歷史詳情，但不出現在預設列表／比價結果。舊 `interactive.py` 改為查詢資料庫，不會因互動查詢爬取來源。

## 資料庫 TLS 與部署驗收

`DB_SSL_CA` 要填真正的 CA 檔案，例如 `/etc/pcpart/mysql-ca.pem`，且 `pcpart` 使用者能讀取。資料庫憑證 SAN 必須符合 `DB_HOST`：若使用 `10.10.0.241`，憑證必須包含該 IP，否則使用憑證對應的內網 DNS 名稱。沒有配置前，不宣稱已驗證資料庫 TLS；不要以關閉驗證來解決憑證不符。

安裝程式會先以 `pcpart` 身分檢查 DB 連線，再建置前端；啟動後 `/api/health/` 必須能查到商品表，才回報安裝完成。`manage.py check --deploy` 的 HTTPS/HSTS 警告需依 Cloudflare Tunnel 架構處理，不應為消除警告就對 HTTP origin 強制 Django HTTPS redirect。

更新後在 LXC 驗收：

```bash
curl -fsS http://127.0.0.1:8080/api/health/
curl -fsS http://127.0.0.1:8080/api/sources/
systemctl status pcpart-api pcpart-sync.timer --no-pager
```

再以正式 HTTPS 網域驗證來源切換、搜尋、雙向比價和 `/admin/` 登入。CSRF 信任來源未明確指定時，預設沿用 `CORS_ALLOWED_ORIGINS`；若 admin 使用另一網域，請在 `CSRF_TRUSTED_ORIGINS` 加入該完整 HTTPS origin。
