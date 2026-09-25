# 安全檢測與驗證（2026-09-25）

範圍：`codex/lxc-dual-source` 原始碼、部署腳本、鎖定套件及本機隔離測試。沒有登入使用者的 LXC、掃描私人網段或操作正式資料庫；這不是正式站滲透測試，也不是無漏洞保證。

## 發現與修正

| 項目 | 結果／修正 |
| --- | --- |
| 前端套件 | npm audit 原有 10 個套件項目：6 high、3 moderate、1 low；相容版本修補後為 0。部分通報屬 Node adapter／建置工具，不代表全部能從公開靜態前端利用。 |
| 後端套件 | 固定 18 個執行依賴版本並用 pip-audit 查詢，0 已知漏洞。MySQL C 擴充以版本資料掃描；本機整合測試使用 SQLite，未驗證 LXC 的 MySQL C 程式庫及 OS 套件。 |
| 同步濫用 | 先驗證權杖；跨 Gunicorn／CLI 鎖定且至少間隔 15 分鐘。Nginx 額外限制同步及讀取 API 請求速率。 |
| 原價屋負載 | 六小時冷卻、robots 規則、403／429／Retry-After 退避、無自動重試、不跟隨重新導向、回應大小上限及連線逾時。詳情比價不連外。 |
| 名稱與連結 | Vue 文字插值處理名稱；外部商品連結僅接受對應來源的 HTTPS 網域，拒絕 script URL、非預期主機、帳密及連接埠。 |
| 錯誤洩漏 | API 不再回傳同步的原始例外；詳細原因只寫伺服器日誌。全形／Unicode 權杖錯誤不再造成比較函式例外。 |
| 部署 | pcpart 使用者執行、NoNewPrivileges、私有同步狀態及 umask、安全 Cookie、Nginx 隱藏版本及阻擋 dotfile。避免要求部分非特權 LXC 不支援的 mount namespace。 |
| 版本庫 | 停止追蹤舊 Python bytecode、Vite 產物與爬蟲日誌。既有 Git 歷史沒有改寫；歷史曾出現的密碼／密鑰仍須輪替。 |

## 驗證

- Django 測試：雙向配對、變體拒絕、下架排除、讀取不連外、舊商品 ID 保留、API 名稱清理、權杖拒絕、程序鎖與冷卻、robots、429／Retry-After、異常頁面、工作中斷恢復。
- 瀏覽器操作：使用本機模擬商品檢查 PChome → 原價屋 → PChome 雙向詳情、價差和通路標示。
- Node 測試：來源網址與惡意 URL 防護；Vite production build。
- `makemigrations --check --dry-run`：無模型變更。
- `bash -n deploy/lxc-install.sh`；部署時仍執行 `nginx -t`。此 macOS 環境未執行 Linux systemd／Nginx。
- Bandit 掃描應用程式碼；B311 僅針對爬蟲延遲使用的非密碼學 random 加上理由註記。

重跑：

```bash
cd pc_crawler_project/forge_backend_server
python manage.py test --settings=forge_backend_server.test_settings
pip-audit --disable-pip --no-deps -r requirements.txt
cd ../../pc-price-frontend
npm test
npm run build
npm audit
```

## 部署上的剩餘事項

- HTTPS redirect 與 HSTS 預設關閉，保留 LXC HTTP 測試。正式流量應在 Cloudflare edge 強制 HTTPS。Nginx 目前以自身協定覆寫 X-Forwarded-Proto；Tunnel origin 是 HTTP 時，不要直接開 Django SSL redirect，否則可能造成迴圈。HTTPS admin 的 CSRF trusted origin 需在 env 填正式網域。
- Nginx 依直連來源 IP 限流；透過 Tunnel 時可能共同計入 Tunnel 主機。需要按真實訪客限流時，先設定可信代理及 Cloudflare 規則，不能直接信任任意客戶端傳來的 IP 標頭。
- 已知 DB 用戶端憑證信任問題尚未解決。手動診斷時略過驗證不等於生產已驗證資料庫身分；後續需配置資料庫 CA 及後端 TLS 驗證。
- 型號匹配採保守規則而非人工商品對照表，可能漏配；即使匹配，也應核對店家包裝、保固及搭購條件。
