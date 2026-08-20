<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import ProductDetail from './components/ProductDetail.vue'

// --- 狀態變數 ---
const products = ref([])
const loading = ref(false)
const error = ref(null)
const searchQuery = ref('') 
const selectedCategory = ref('') 
const systemLastUpdated = ref('')

// [新增] 分頁控制變數
const nextPage = ref(null)     // 存放下一頁的 API 網址
const prevPage = ref(null)     // 存放上一頁的 API 網址
const totalCount = ref(0)      // 資料庫總筆數

// 控制頁面狀態
const selectedProduct = ref(null)

// --- 手動同步相關狀態 ---
const syncing = ref(false)
const syncResult = ref(null)   // 上次同步結果摘要
const syncError = ref(null)

// 後端 API 網址
//const API_URL = 'http://192.168.0.242:8000/api/products/'
const currentHost = window.location.hostname

let API_URL = ''

// === [關鍵修改] 智慧判斷邏輯 ===
if (currentHost === '192.168.0.243') {
  // 情況 A：如果你在「內網」連前端 (.243)
  // 強制指引它去連「後端機器 (.242)」
  API_URL = 'http://192.168.0.242:8000/api/products/'
} else {
  // 情況 B：如果你在「外網」連線 (例如 123.110.x.x)
  // 假設你的路由器有設定 Port 8000 轉發到後端，那就直接用當前的 IP
  API_URL = `http://${currentHost}:8000/api/products/`
}

const SYNC_URL = API_URL.replace('/api/products/', '/api/sync/')

// 分類選項
const CATEGORIES = [
  { value: '', label: '所有分類' },
  { value: 'GPU', label: '顯示卡 (GPU)' },
  { value: 'CPU', label: '處理器 (CPU)' },
  { value: 'MB', label: '主機板 (MB)' },
  { value: 'RAM', label: '記憶體 (RAM)' },
  { value: 'SSD', label: '固態硬碟 (SSD)' },
  { value: 'HDD', label: '傳統硬碟 (HDD)' },
  { value: 'PSU', label: '電源供應器 (PSU)' },
  { value: 'OTHER', label: '其他配件 (Other)' },
]

const openDetail = (item) => {
  selectedProduct.value = item
  window.scrollTo(0, 0)
}

const backToList = () => {
  selectedProduct.value = null
}

// === [核心修改] 支援分頁的抓取函式 ===
// url 參數：預設使用 API_URL (第一頁)，也可以傳入 nextPage 或 prevPage
const fetchProducts = async (url = API_URL) => {
  loading.value = true
  error.value = null
  
  // 如果是重新搜尋 (url 是首頁)，清空列表製造重讀感
  if (url === API_URL) {
    products.value = []
  }

  try {
    const params = {}
    
    // 注意：只有在「搜尋/篩選」時 (url === API_URL) 才需要手動帶參數
    // 如果是「換頁」 (url !== API_URL)，Django 回傳的 next 網址已經包含參數了 (例如 ?page=2&search=RTX)
    if (url === API_URL) {
      if (searchQuery.value) params.search = searchQuery.value
      if (selectedCategory.value) params.category = selectedCategory.value
    }

    const response = await axios.get(url, { params })
    
    // 處理 DRF 分頁格式
    if (response.data.results) {
      products.value = response.data.results  // 商品資料在 .results
      nextPage.value = response.data.next     // 下一頁網址
      prevPage.value = response.data.previous // 上一頁網址
      totalCount.value = response.data.count  // 總筆數
    } else {
      // 如果後端沒開分頁 (相容性)
      products.value = response.data
      nextPage.value = null
      prevPage.value = null
      totalCount.value = response.data.length
    }
    
    systemLastUpdated.value = new Date().toLocaleString('zh-TW')
    console.log(`取得 ${products.value.length} 筆資料 (總數: ${totalCount.value})`)

  } catch (err) {
    console.error("連線失敗:", err)
    error.value = "無法連線到後端，請檢查 Django 伺服器狀態。"
  } finally {
    loading.value = false
    // 如果是換頁，自動捲動到最上方
    if (url !== API_URL) window.scrollTo({ top: 0, behavior: 'smooth' })
  }
}

// 當分類改變時，從第一頁重新搜尋
const onCategoryChange = () => {
  fetchProducts(API_URL)
}

// === 手動同步 ===
// 這個按鈕只給網站管理者用，一般訪客按了不會有反應（後端會擋掉）。
// 權杖只存在這次瀏覽的記憶體裡，重新整理頁面就要重新輸入，
// 故意不存進 localStorage，避免長期留在瀏覽器裡外洩。
let syncToken = ''

const runSync = async () => {
  if (!syncToken) {
    syncToken = window.prompt('請輸入管理員同步權杖 (Sync Token)：') || ''
    if (!syncToken) return
  }

  syncing.value = true
  syncResult.value = null
  syncError.value = null

  try {
    const response = await axios.post(SYNC_URL, {}, {
      headers: { 'X-Sync-Token': syncToken },
      timeout: 5 * 60 * 1000, // 同步可能要跑幾十秒到幾分鐘，拉長逾時時間
    })
    syncResult.value = response.data
    // 同步完重新整理商品列表，讓使用者馬上看到最新結果
    await fetchProducts(API_URL)
  } catch (err) {
    if (err.response?.status === 403) {
      syncError.value = '權杖錯誤，請確認同步權杖是否正確。'
      syncToken = '' // 權杖錯誤就清掉，下次重新問
    } else {
      syncError.value = err.response?.data?.error || '同步失敗，請確認後端伺服器狀態。'
    }
  } finally {
    syncing.value = false
  }
}

onMounted(() => {
  fetchProducts()
})
</script>

<template>
  <div class="min-h-screen bg-gray-50 p-6 font-sans relative">
    
    <div v-if="selectedProduct" class="max-w-7xl mx-auto py-6">
      <ProductDetail :product="selectedProduct" @back="backToList" />
    </div>

    <div v-else class="max-w-7xl mx-auto">
      
      <div class="flex flex-col items-center justify-center mb-10 space-y-6">
        <div class="text-center relative w-full">
          <h1 class="text-4xl font-extrabold text-gray-800 tracking-tight">電腦零件比價網</h1>
          <p class="text-gray-500 mt-2">
            共找到 <span class="text-blue-600 font-bold">{{ totalCount }}</span> 筆商品
          </p>

          <button
            @click="runSync"
            :disabled="syncing"
            title="管理員專用：手動觸發爬蟲同步最新價格"
            class="absolute right-0 top-0 text-xs px-3 py-1.5 rounded-full border transition-colors flex items-center gap-1.5"
            :class="syncing ? 'bg-gray-100 text-gray-400 border-gray-200 cursor-wait' : 'bg-white text-gray-500 border-gray-300 hover:border-blue-400 hover:text-blue-600'">
            <svg class="h-3.5 w-3.5" :class="syncing ? 'animate-spin' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            {{ syncing ? '同步中，請稍候…' : '立即更新' }}
          </button>
        </div>

        <div v-if="syncResult" class="w-full max-w-3xl bg-green-50 border border-green-200 text-green-800 text-sm rounded-lg px-4 py-3 flex flex-wrap gap-x-4 gap-y-1 items-center">
          <span class="font-bold">✅ 同步完成（耗時 {{ syncResult.duration_seconds }} 秒）</span>
          <span>掃描 {{ syncResult.scanned }} 筆</span>
          <span>新增 {{ syncResult.new_products }}</span>
          <span>價格更新 {{ syncResult.price_updated }}</span>
          <span>下架 {{ syncResult.delisted }}</span>
          <button @click="syncResult = null" class="ml-auto text-green-600 hover:text-green-800">✕</button>
        </div>
        <div v-if="syncError" class="w-full max-w-3xl bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3 flex items-center justify-between">
          <span>⚠️ {{ syncError }}</span>
          <button @click="syncError = null" class="text-red-500 hover:text-red-700">✕</button>
        </div>

        <div class="w-full max-w-3xl relative flex items-center shadow-lg rounded-full overflow-hidden border border-gray-200 bg-white focus-within:ring-2 focus-within:ring-blue-400">
          <div class="relative border-r border-gray-200 bg-gray-50 hover:bg-gray-100 transition-colors shrink-0 min-w-[160px]">
            <select 
              v-model="selectedCategory" 
              @change="onCategoryChange"
              class="appearance-none bg-transparent py-4 pl-6 pr-10 outline-none cursor-pointer font-medium text-gray-700 h-full w-full">
              <option v-for="cat in CATEGORIES" :key="cat.value" :value="cat.value">
                {{ cat.label }}
              </option>
            </select>
            <div class="pointer-events-none absolute inset-y-0 right-0 flex items-center px-3 text-gray-500">
              <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
            </div>
          </div>

          <input 
            v-model="searchQuery" 
            @keyup.enter="fetchProducts(API_URL)" 
            type="text" 
            class="w-full pl-6 pr-4 py-4 text-gray-700 bg-transparent focus:outline-none text-lg placeholder-gray-400"
            placeholder="請輸入關鍵字 (例如: RTX 4090, DDR5...)" 
          />
          
          <button @click="fetchProducts(API_URL)" class="bg-blue-600 hover:bg-blue-700 text-white p-4 px-6 flex items-center justify-center transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
          </button>
        </div>
      </div>

      <div v-if="error" class="max-w-2xl mx-auto bg-red-100 border-l-4 border-red-500 text-red-700 p-4 rounded mb-8 shadow-sm flex items-start gap-3">
        <span class="text-xl">⚠️</span>
        <div><p class="font-bold">連線錯誤</p><p class="text-sm mt-1">{{ error }}</p></div>
      </div>

      <div v-if="loading" class="flex flex-col justify-center items-center py-20 text-gray-500">
        <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
        <span>正在載入資料...</span>
      </div>

      <div v-else>
        <div v-if="products.length > 0" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 mb-12">
          <div 
            v-for="item in products" :key="item.id" 
            @click="openDetail(item)"
            class="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden hover:shadow-xl hover:-translate-y-1 hover:ring-2 hover:ring-blue-500/20 transition-all duration-300 group cursor-pointer flex flex-col h-full">
            
            <div class="h-48 bg-gray-50 flex items-center justify-center relative p-4 shrink-0">
              <img v-if="item.pic_url" :src="item.pic_url" :alt="item.name" class="object-contain h-full w-full mix-blend-multiply group-hover:scale-110 transition-transform duration-500" />
              <div v-else class="text-gray-300 flex flex-col items-center"><span class="text-xs">無圖片</span></div>
              
              <span class="absolute top-3 right-3 text-[10px] font-bold px-2 py-1 rounded-md uppercase tracking-wider shadow-sm"
                :class="{
                  'bg-blue-100 text-blue-700': item.category === 'MB',
                  'bg-red-100 text-red-700': item.category === 'GPU',
                  'bg-green-100 text-green-700': item.category === 'CPU',
                  'bg-purple-100 text-purple-700': item.category === 'RAM',
                  'bg-orange-100 text-orange-700': item.category === 'PSU',
                  'bg-gray-100 text-gray-700': !['MB','GPU','CPU','RAM','PSU'].includes(item.category)
                }">
                {{ item.category }}
              </span>
            </div>

            <div class="p-4 flex flex-col flex-grow">
              <h2 class="text-gray-800 font-bold text-base leading-snug line-clamp-2 h-10 mb-2 group-hover:text-blue-600 transition-colors" :title="item.name">
                {{ item.name }}
              </h2>
              
              <div class="flex flex-wrap gap-1 mb-3 h-12 content-start overflow-hidden">
                <template v-if="item.specs && Object.keys(item.specs).length > 0">
                  <span v-for="(val, key) in item.specs" :key="key" class="text-[10px] bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded border border-gray-200">{{ val }}</span>
                </template>
                <span v-else class="text-xs text-gray-400 italic">尚無詳細規格</span>
              </div>

              <div class="mt-auto border-t border-gray-50 pt-3 flex items-end justify-between">
                <div class="flex flex-col">
                  <span class="text-xs text-gray-400">最新價格</span>
                  <span class="text-xl font-extrabold text-red-600">${{ (item.latest_price || item.price || 0).toLocaleString() }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="!loading && products.length === 0" class="text-center py-20 text-gray-500 bg-white rounded-xl border border-dashed border-gray-200">
          <div class="text-6xl mb-4">🔍</div>
          <h3 class="text-lg font-medium text-gray-700">找不到相關商品</h3>
          <p class="mt-2">試著切換分類，或是使用更簡單的關鍵字搜尋。</p>
          <button @click="searchQuery=''; selectedCategory=''; fetchProducts(API_URL)" class="mt-4 text-blue-600 hover:underline">
            清除所有篩選條件
          </button>
        </div>

        <div v-if="!loading && products.length > 0" class="flex justify-center items-center gap-4 pb-20">
          <button 
            @click="fetchProducts(prevPage)" 
            :disabled="!prevPage"
            class="px-6 py-3 rounded-lg font-medium transition-colors border shadow-sm"
            :class="prevPage ? 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50 hover:text-blue-600' : 'bg-gray-100 text-gray-400 cursor-not-allowed border-transparent'">
            ← 上一頁
          </button>
          
          <span class="text-gray-500 text-sm">
            本頁顯示 {{ products.length }} 筆
          </span>

          <button 
            @click="fetchProducts(nextPage)" 
            :disabled="!nextPage"
            class="px-6 py-3 rounded-lg font-medium transition-colors border shadow-sm"
            :class="nextPage ? 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50 hover:text-blue-600' : 'bg-gray-100 text-gray-400 cursor-not-allowed border-transparent'">
            下一頁 →
          </button>
        </div>

      </div>
    </div>

    <div class="fixed bottom-4 right-4 bg-white/90 backdrop-blur-sm border border-gray-200 shadow-lg rounded-full px-4 py-2 text-xs text-gray-500 flex items-center gap-2 z-50 transition-opacity duration-300" :class="loading ? 'opacity-50' : 'opacity-100'">
      <div class="w-2 h-2 rounded-full" :class="error ? 'bg-red-500' : 'bg-green-500 animate-pulse'"></div>
      <span v-if="error">連線異常</span>
      <span v-else>系統連線正常 ({{ systemLastUpdated }})</span>
    </div>

  </div>
</template>
