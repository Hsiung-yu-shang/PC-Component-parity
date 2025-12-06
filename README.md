# 🖥️ PC Parts Intelligence - 電腦零件智慧比價平台

這是一個基於 **Python Django** 與 **Vue 3** 的全端開發專案，旨在解決電腦組裝時「比價」與「規格相容性」的痛點。

系統透過自動化爬蟲定期抓取電商（如 PChome）資料，並透過 **Regex 規則引擎** 自動分析零件規格（如 DDR4/DDR5、CPU 腳位、顯卡型號），在使用者瀏覽時提供即時的 **相容性警告** 與 **購買建議**。

---

## 🚀 核心功能 (Key Features)

### 1. 🕷️ 自動化價格追蹤
* **定期爬蟲**：排程腳本自動抓取最新價格。
* **歷史價格**：記錄每次爬取的價格波動，讓使用者知道何時是最佳買點。
* **資料清洗**：自動過濾非零件商品（如筆電、周邊）並處理 Emoji 編碼問題。

### 2. 🧠 智慧規格分析 (Smart Specs Engine)
系統內建 Python 規則引擎，能從雜亂的商品標題中自動提取結構化資料：
* **自動分類**：識別 GPU, CPU, MB, RAM, SSD, HDD, PSU。
* **規格提取**：
    * **顯卡**：自動抓取型號（如 `RTX 4090`）與顯存（`24G`）。
    * **硬碟**：區分 `M.2` / `SATA` 介面，識別 `PCIe Gen4` / `Gen5` 速度。
    * **電源**：自動提取瓦數（`850W`）與轉換效率（`金牌`）。

### 3. 🛡️ 智慧相容性提醒 (Compatibility Check)
前端 Vue.js 依照規格資料，即時提醒使用者：
* ⚠️ **記憶體防呆**：選購 DDR5 記憶體時，提醒需搭配支援 DDR5 的主機板。
* ⚠️ **CPU 腳位**：提醒 LGA1700 或 AM5 的主機板匹配。
* ⚡ **電源建議**：瀏覽高階顯卡時，自動建議搭配 850W 以上電源。

### 4. ⚡ 現代化前後端架構
* **Server-side Searching**：透過 Django DRF 處理搜尋與過濾，支援大量資料查詢。
* **Smart IP Switching**：前端自動判斷使用者是「內網」還是「外網」，自動切換 API 連線目標。

---

## 🛠️ 系統架構 (System Architecture)

本專案採用 **前後端分離 (Headless)** 架構，部署於 Rocky Linux 環境。

| 角色 | 技術堆疊 | 部署位置 | IP (範例) | Port |
| :--- | :--- | :--- | :--- | :--- |
| **Frontend** | Vue 3, Vite, Tailwind CSS | Frontend Server | `192.168.0.243` | `8080` |
| **Backend** | Python 3, Django, DRF | Rocky Linux | `192.168.0.242` | `8000` |
| **Database** | MySQL 8.0 | Rocky Linux | `192.168.0.241` | `3306` |
| **Crawler** | Requests, Custom Regex | Rocky Linux | `192.168.0.242` | - |

### 網路拓樸
```mermaid
graph LR
    User["使用者 (手機/電腦)"] -- "公網 IP" --> Router

    subgraph LAN ["區網 (LAN)"]
        Router -- "Port 8080" --> Frontend["Vue 前端 (.243)"]
        Router -- "Port 8000" --> Backend["Django API (.242)"]
        Backend -- "SQL" --> DB[("MySQL 資料庫")]
        Crawler["爬蟲腳本"] -- "寫入" --> DB
    end
