<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import axios from 'axios'
import ProductDetail from './components/ProductDetail.vue'
import { createRequestGate, productPageUrl } from './requestGate'
const api = axios.create({ timeout: 12000 })
const listGate = createRequestGate()
const detailGate = createRequestGate()
const sources = ref([])
const sourceError = ref('')
const tokenDialog = ref(null)
const tokenInput = ref('')
let disposed = false

// --- 狀態變數 ---
const products = ref([])
const loading = ref(false)
const error = ref(null)
const searchQuery = ref('')
const selectedCategory = ref('')
const selectedSource = ref('')
const systemLastUpdated = ref('')

// [新增] 分頁控制變數
const nextPage = ref(null)     // 存放下一頁的 API 網址
const prevPage = ref(null)     // 存放上一頁的 API 網址
const totalCount = ref(0)      // 資料庫總筆數

// 控制頁面狀態
const selectedProduct = ref(null)
const detailLoading = ref(false)
const detailError = ref('')
const syncing = ref(false)
const syncMessage = ref('')

// Nginx serves the API on the same origin. Vite proxies this path in development.
const API_URL = '/api/products/'
const SYNC_URL = '/api/sync/'

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
  { value: 'CASE', label: '機殼 (CASE)' },
  { value: 'OTHER', label: '其他配件 (Other)' },
]

const openDetail = async (item) => {
  const request = detailGate.begin()
  selectedProduct.value = item
  detailLoading.value = true
  detailError.value = ''
  window.scrollTo(0, 0)
  try {
    const response = await api.get(`${API_URL}${encodeURIComponent(item.id)}/`, { signal: request.signal })
    if (request.isCurrent()) selectedProduct.value = response.data
  } catch (err) {
    if (request.isCurrent()) detailError.value = '商品詳情與比價載入失敗。'
  } finally {
    if (request.isCurrent()) detailLoading.value = false
  }
}

const backToList = () => {
  detailGate.cancel()
  selectedProduct.value = null
}

// === [核心修改] 支援分頁的抓取函式 ===
// url 參數：預設使用 API_URL (第一頁)，也可以傳入 nextPage 或 prevPage
const fetchProducts = async (url = API_URL) => {
  if (!url) return
  const request = listGate.begin()
  loading.value = true
  error.value = null
  nextPage.value = null
  prevPage.value = null
  totalCount.value = 0

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
      if (selectedSource.value) params.source = selectedSource.value
    }

    const requestUrl = productPageUrl(url, window.location.origin)
    const response = await api.get(requestUrl, { params, signal: request.signal })
    if (!request.isCurrent()) return

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


  } catch (err) {
    if (!request.isCurrent()) return
    products.value = []
    error.value = err.response?.status === 429 ? '請求較頻繁，請稍後再試。' : '商品載入失敗，請稍後重試。'
  } finally {
    if (!request.isCurrent()) return
    loading.value = false
    // 如果是換頁，自動捲動到最上方
    if (url !== API_URL) window.scrollTo({ top: 0, behavior: 'smooth' })
  }
}

// 當分類改變時，從第一頁重新搜尋
const onCategoryChange = () => {
  fetchProducts(API_URL)
}

const loadSources = async () => {
  sourceError.value = ''
  try {
    const { data } = await api.get('/api/sources/')
    if (!disposed) sources.value = data
  } catch {
    sourceError.value = '來源清單載入失敗。'
  }
}

const requestSync = () => {
  tokenInput.value = ''
  tokenDialog.value.showModal()
}
const runSync = async () => {
  const token = tokenInput.value
  tokenInput.value = ''
  tokenDialog.value.close()
  if (!token || syncing.value) return
  syncing.value = true
  syncMessage.value = '正在啟動同步…'
  const headers = { 'X-Sync-Token': token }
  try {
    const body = selectedSource.value ? { sources: [selectedSource.value] } : {}
    await api.post(SYNC_URL, body, { headers })
    for (let attempt = 0; attempt < 120 && !disposed; attempt++) {
      await new Promise(resolve => setTimeout(resolve, 3000))
      if (disposed) return
      const { data } = await api.get(`${SYNC_URL}status/`, { headers })
      if (data.state === 'done') {
        const notes = Object.entries(data.summary.sources || {}).map(([key, result]) => {
          const label = sources.value.find(s => s.id === key)?.label || key
          const descriptions = { cached: '冷卻中，沿用舊價格', backoff: '暫停更新，沿用舊價格', empty: '未取得商品，保留舊資料', updated: '已更新' }
          return `${label}：${descriptions[result.state] || result.state}`
        }).join('；')
        syncMessage.value = `同步結束：掃描 ${data.summary.scanned} 筆，價格更新 ${data.summary.price_updated} 筆。${notes}`
        await fetchProducts(API_URL)
        return
      }
      if (data.state === 'error') throw new Error(data.error || '同步失敗')
    }
    syncMessage.value = '同步仍在執行，請稍後重新載入商品。'
  } catch (err) {
    // Never log the Axios error object: it contains the authorization header.
    const detail = err.response?.data?.sources || err.response?.data?.detail
    syncMessage.value = err.response?.status === 403 ? '同步權杖無效。' : (detail?.toString() || `同步失敗：${err.message}`)
  } finally {
    syncing.value = false
  }
}

onMounted(() => {
  loadSources()
  fetchProducts()
})
onUnmounted(() => { disposed = true; listGate.cancel(); detailGate.cancel() })
</script>

<template>
  <dialog ref="tokenDialog" @cancel="tokenInput = ''" class="rounded-xl p-6 shadow-xl w-full max-w-md backdrop:bg-black/40">
    <form @submit.prevent="runSync">
      <h2 class="font-bold text-lg">管理員同步</h2>
      <p class="text-sm text-gray-600 mt-2">更新所選來源；選擇全部時，更新所有啟用的來源。既有冷卻限制仍適用。</p>
      <label for="sync-token" class="block mt-4 text-sm">同步權杖</label>
      <input id="sync-token" v-model="tokenInput" type="password" autocomplete="off" required class="w-full border rounded p-2 mt-1" />
      <div class="flex justify-end gap-3 mt-4">
        <button type="button" @click="tokenInput = ''; tokenDialog.close()" class="px-3 py-2">取消</button>
        <button type="submit" class="bg-blue-600 text-white rounded px-3 py-2">開始同步</button>
      </div>
    </form>
  </dialog>
  <div class="min-h-screen bg-gray-50 p-6 font-sans relative">

    <div v-if="selectedProduct" class="max-w-7xl mx-auto py-6">
      <ProductDetail :product="selectedProduct" :loading="detailLoading" :error="detailError" @back="backToList" @open="openDetail" @retry="openDetail(selectedProduct)" />
    </div>

    <div v-else class="max-w-7xl mx-auto">

      <div class="flex flex-col items-center justify-center mb-10 space-y-6">
        <div class="text-center">
          <h1 class="text-4xl font-extrabold text-gray-800 tracking-tight">電腦零件比價網</h1>
          <p class="text-gray-500 mt-2">
            共找到 <span class="text-blue-600 font-bold">{{ totalCount }}</span> 筆商品
          </p>
        </div>

        <button @click="requestSync" :disabled="syncing" class="rounded border border-gray-300 bg-white px-3 py-1 text-xs text-gray-600 disabled:opacity-50">{{ syncing ? '同步中…' : '管理員更新所選來源' }}</button>
        <p v-if="syncMessage" class="text-sm text-gray-600">{{ syncMessage }}</p>

        <p v-if="sourceError" class="text-sm text-red-700">{{ sourceError }} <button @click="loadSources" class="underline">重試</button></p>
        <div class="flex justify-center items-center gap-2 text-sm">
          <label for="source-filter" class="text-gray-600">資料來源</label>
          <select id="source-filter" v-model="selectedSource" @change="fetchProducts(API_URL)" class="rounded border border-gray-300 bg-white px-3 py-2">
            <option value="">全部</option>
            <option v-for="source in sources" :key="source.id" :value="source.id">{{ source.label }}（{{ source.channel }}）{{ source.sync_enabled ? '' : ' · 暫停更新' }}</option>
          </select>
        </div>

        <div class="w-full max-w-3xl relative flex items-center shadow-lg rounded-full overflow-hidden border border-gray-200 bg-white focus-within:ring-2 focus-within:ring-blue-400">
          <div class="relative border-r border-gray-200 bg-gray-50 hover:bg-gray-100 transition-colors shrink-0 w-28 sm:w-40">
            <select
              v-model="selectedCategory" aria-label="商品分類"
              @change="onCategoryChange"
              class="appearance-none bg-transparent py-4 pl-2 sm:pl-6 pr-6 outline-none text-sm cursor-pointer font-medium text-gray-700 h-full w-full">
              <option v-for="cat in CATEGORIES" :key="cat.value" :value="cat.value">
                {{ cat.label }}
              </option>
            </select>
            <div class="pointer-events-none absolute inset-y-0 right-0 flex items-center px-3 text-gray-500">
              <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
            </div>
          </div>

          <input
            v-model="searchQuery" maxlength="200" aria-label="搜尋關鍵字"
            @keyup.enter="fetchProducts(API_URL)"
            type="text"
            class="min-w-0 w-full pl-3 pr-2 py-4 text-gray-700 bg-transparent focus:outline-none text-lg placeholder-gray-400"
            placeholder="請輸入關鍵字 (例如: RTX 4090, DDR5...)"
          />

          <button aria-label="搜尋商品" @click="fetchProducts(API_URL)" class="bg-blue-600 hover:bg-blue-700 text-white p-4 px-3 sm:px-6 flex items-center justify-center transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
          </button>
        </div>
      </div>

      <div v-if="error" class="max-w-2xl mx-auto bg-red-100 border-l-4 border-red-500 text-red-700 p-4 rounded mb-8 shadow-sm flex items-start gap-3">
        <span class="text-xl">⚠️</span>
        <div><p class="font-bold">載入失敗</p><p class="text-sm mt-1">{{ error }}</p><button @click="fetchProducts(API_URL)" class="mt-2 underline">重新載入</button></div>
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
            @keydown.enter="openDetail(item)"
            @keydown.space.prevent="openDetail(item)"
            tabindex="0" role="button" :aria-label="`查看 ${item.name}`"
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
              <span class="text-xs text-gray-500 mb-2">{{ item.source_label || item.source }} · {{ item.channel }}</span>

              <div class="flex flex-wrap gap-1 mb-3 h-12 content-start overflow-hidden">
                <template v-if="item.specs && Object.keys(item.specs).length > 0">
                  <span v-for="(val, key) in item.specs" :key="key" class="text-[10px] bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded border border-gray-200">{{ val }}</span>
                </template>
                <span v-else class="text-xs text-gray-400 italic">尚無詳細規格</span>
              </div>

              <p v-if="item.price_stale" class="text-xs text-amber-700 mb-2">價格較久未更新，請向通路確認。</p>
              <div class="mt-auto border-t border-gray-50 pt-3 flex items-end justify-between">
                <div class="flex flex-col">
                  <span class="text-xs text-gray-400">最新價格</span>
                  <span class="text-xl font-extrabold text-red-600">{{ item.latest_price == null ? '尚無報價' : `NT$ ${item.latest_price.toLocaleString()}` }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="!loading && !error && products.length === 0" class="text-center py-20 text-gray-500 bg-white rounded-xl border border-dashed border-gray-200">
          <div class="text-6xl mb-4">🔍</div>
          <h3 class="text-lg font-medium text-gray-700">找不到相關商品</h3>
          <p class="mt-2">試著切換分類，或是使用更簡單的關鍵字搜尋。</p>
          <button @click="searchQuery=''; selectedCategory=''; selectedSource=''; fetchProducts(API_URL)" class="mt-4 text-blue-600 hover:underline">
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
      <span v-else>上次載入：{{ systemLastUpdated || '尚未完成' }}</span>
    </div>

  </div>
</template>
