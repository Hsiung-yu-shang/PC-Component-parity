# 完整程式審查（2026-09-27）

範圍：測試分支的 Django API、同步流程、兩個來源解析、Vue 商品列表／詳情、管理權杖、來源設定、舊命令列入口與 LXC 安裝腳本。審查基準為 `206d64e`，以下修正保留在 `codex/lxc-dual-source`，不合併 main。

## 此次發現與處理

| 優先級 | 發現 | 修正與證據 |
| --- | --- | --- |
| P1 | 單一來源異常或商品格式錯誤可中斷整次同步 | PChome 有界回應、格式驗證、持久退避；來源錯誤不阻止另一來源。測試驗證 PChome 失敗後仍儲存原價屋商品。資料庫錯誤仍明確失敗，不假裝成功。 |
| P1 | 安裝只檢查靜態首頁，無法確認 API／DB 可用 | 建置前以服務帳號檢查 DB，啟動後重試 `/api/health/`，必須成功查詢商品表才回報完成。部署腳本通過語法檢查；Linux 執行仍待 LXC 驗收。 |
| P2 | CPU 名称開頭年份可能當成型號；下架基準受新增商品干擾 | 改用 CPU 型號上下文，加入不同 CPU 不得因年份配對的測試；抓取前記錄既有數量、排除重複搜尋結果，部分目錄不下架。 |
| P2 | 詳情載入全部歷史／評論、評論作者造成額外查詢 | 預覽上限各 100 筆，完整紀錄新增 20 筆分頁 API，評論合併作者查詢。105 筆資料測試及固定查詢數驗證。 |
| P2 | 切换來源或商品時，較慢舊請求可能蓋掉新結果 | AbortController 與請求序號檢查；相同商品重新載入也適用，分頁固定使用同源商品 API。Node 回歸測試。 |
| P2 | 管理員 session 與同步 token 驗證混用，可能出現 CSRF 拒絕 | 同步端點僅使用專用 token 權限；測試已登入 staff + 正確 token 成功，無 token 仍拒絕。Admin 自身 CSRF 保護保留。 |
| P2 | 源資料異常價格／ID／圖片地址可能破壞儲存或導向非預期圖片主機 | 限制價格範圍、ID 字元及長度，圖片只組合預期主機的路徑；未知通路無購買連結。 |
| P2 | 舊 `pchome_core.py` 保留不同版本爬蟲，可繞過共用保護 | 改為共用爬蟲＋同步鎖的相容入口；互動查詢改為只讀資料庫，不再直接爬取。 |
| P3 | 無價格呈現 0 元、舊價格無提示、相容性說明過度概括 | 顯示「尚無報價」、最後確認時間與過期提醒、下架提示；移除固定電源瓦數及不適用所有腳位的 CPU 範例。 |
| P3 | 來源名稱與同步範圍寫死，無法從 env 控制 | 來源登錄表、來源 API、動態選單、選定來源同步、env 關鍵字／頁數／啟用來源／延長冷卻。未知來源在部署 check 即拒絕。 |

## 驗證結果

- Django：29 項測試通過，含原有 20 組配對案例；使用隔離 SQLite，不接正式 DB。
- Node：5 項測試通過；production build 成功。
- npm audit（含開發工具）：0 已知漏洞；pip-audit 固定 requirements：0 已知漏洞。
- Bandit：掃描整個 `pc_crawler_project`，排除測試檔。0 high／0 medium，1 low（`batch_job.py` 使用 `os.execv`）；人工確認為固定 Python 與固定 manage.py、參數陣列，不經 shell，屬預期相容入口。另一次包含 test_settings 的掃描提示測試用假密碼，與生產設定無關。
- `makemigrations --check --dry-run` 無模型變更；`bash -n` 與 `git diff --check` 通過。
- 本機 HTTP `/api/health/` 回應 200。瀏覽器使用本機 SQLite 測試商品，驗證雙向比價、來源切換、名稱清理、過期與無報價提示、密碼型權杖輸入及取消。手機寬度檢查無橫向溢出；未操作正式站同步。

## 尚需部署環境確認

1. **資料庫 TLS 身分驗證**：提供 `DB_SSL_CA` 支援 VERIFY_IDENTITY，但既有憑證信任問題未能在此環境解決；須配置 CA、符合 DB_HOST 的憑證與檔案權限。空白 CA 不代表已驗證 TLS。
2. **正式入口防護**：Cloudflare HTTPS、admin 登入、CSRF origin、LXC 防火牆、MySQL 使用者限制與 OS 套件，仍需實機確認。Gunicorn 僅綁 loopback。不要為了消除 check 警告對 HTTP Tunnel origin 直接啟用 Django SSL redirect。
3. **來源限制**：原價屋頁面六小時最低間隔、robots 與退避可降低負載；無法保證不封鎖。未大量抓取真實來源作為測試。
4. **資料完整度**：PChome 是關鍵字取樣；未找到配對不等於沒有販售。自動配對不是人工型號目錄，應核對包裝、保固、顏色與搭購條件。未增加評論投稿、歷史圖表等原本不存在的前台功能。
5. **舊密鑰**：Git 歷史曾出現的密碼須輪替，這次沒有改寫历史或讀取／輸出正式密碼。
6. **限流與部署**：Tunnel 代理 IP 可能共用 Nginx 額度；大量流量需另設可信代理或 Cloudflare 限流。安裝器就地更新，不提供原子發版／自動回滾，更新時可能短暫中斷，先在測試 LXC 驗收。

以上是程式審查及有限測試，不是正式站滲透測試，也不能保證沒有未知漏洞。

---

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
