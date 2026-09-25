<script setup>
import { computed } from 'vue'
import { storeUrl } from '../storeUrl'

// 接收父層傳來的商品資料
const props = defineProps({
  loading: Boolean,
  error: { type: String, default: '' },
  product: {
    type: Object,
    required: true
  }
})

// 定義「返回」事件，通知父層切換回列表
const emit = defineEmits(['back', 'open', 'retry'])

// 格式化日期
const formatDate = (dateString) => {
  if (!dateString) return ''
  return new Date(dateString).toLocaleDateString('zh-TW')
}

const goToStore = () => {
  window.open(storeUrl(props.product), '_blank', 'noopener,noreferrer')
}

const otherStore = computed(() => props.product.source === 'coolpc' ? 'PChome' : '原價屋')
const priceDifference = (price) => {
  if (props.product.latest_price == null) return ''
  const delta = price - props.product.latest_price
  return delta === 0 ? '與本頁商品同價' : `比本頁商品${delta < 0 ? '便宜' : '貴'} NT$ ${Math.abs(delta).toLocaleString()}`
}

// === [核心功能] 智慧相容性檢查引擎 ===
const smartTips = computed(() => {
  const p = props.product
  const specs = p.specs || {}
  const tips = []

  // 1. 記憶體 (RAM) 檢查
  if (p.category === 'RAM') {
    if (specs.memory_type) {
      tips.push({
        type: 'warning',
        title: '!!主機板相容性注意',
        msg: `您正在查看 **${specs.memory_type}** 記憶體。購買前請務必確認您的主機板規格表有標示支援 "${specs.memory_type}" 插槽（DDR4 與 DDR5 插槽物理不相容）。`
      })
    }
  }

  // 2. 主機板 (MB) 檢查
  if (p.category === 'MB') {
    if (specs.memory_type) { // 這裡要注意 pchome_core.py 解析出來的 key 是 memory_type 還是 memory
      tips.push({
        type: 'info',
        title: '!!記憶體選購指南',
        msg: `此主機板僅支援 **${specs.memory_type}** 規格記憶體，請勿購買錯誤版本。`
      })
    }
    if (specs.socket) {
      tips.push({
        type: 'info',
        title: '!!CPU 搭配建議',
        msg: `此主機板腳位為 **${specs.socket}**，請搭配對應的處理器（例如：Intel 12/13/14代 或 AMD Ryzen 7000系列）。`
      })
    }
  }

  // 3. 處理器 (CPU) 檢查
  if (p.category === 'CPU') {
    if (specs.socket) {
      tips.push({
        type: 'warning',
        title: '!!腳位匹配提醒',
        msg: `此 CPU 使用 **${specs.socket}** 腳位，請搭配支援 ${specs.socket} 晶片組的主機板。`
      })
    }
  }

  // 4. 固態硬碟 (SSD) 檢查
  if (p.category === 'SSD') {
    if (specs.interface === 'M.2') {
      tips.push({
        type: 'info',
        title: '!!插槽確認',
        msg: `這是 **M.2** 介面的 SSD (${specs.pcie_ver || 'PCIe'})，請確認主機板有 M.2 插槽並支援該速度以發揮最大效能。`
      })
    }
  }

  // 5. 顯示卡 (GPU) 檢查
  if (p.category === 'GPU') {
    tips.push({
      type: 'warning',
      title: '!!電源瓦數建議',
      msg: '高階顯示卡瞬間功耗較大，建議搭配 **750W 或 850W 以上** 的金牌電源供應器，並確認機殼長度是否足夠容納顯卡。'
    })
  }

  return tips
})
</script>

<template>
  <div class="max-w-5xl mx-auto bg-white rounded-2xl shadow-xl overflow-hidden border border-gray-100">
    
    <div class="bg-gray-50 px-6 py-4 border-b border-gray-200 flex items-center justify-between">
      <button 
        @click="emit('back')" 
        class="flex items-center text-gray-600 hover:text-blue-600 font-medium transition-colors">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-1" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clip-rule="evenodd" />
        </svg>
        返回列表
      </button>
      <span class="text-xs text-gray-500">{{ product.source === 'coolpc' ? '原價屋 · 實體通路' : 'PChome · 線上購物' }}</span>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-0">
      
      <div class="p-8 bg-gray-50 flex items-center justify-center border-b md:border-b-0 md:border-r border-gray-200">
        <img v-if="product.pic_url" :src="product.pic_url" :alt="product.name" class="max-w-full max-h-[400px] object-contain mix-blend-multiply" />
        <div v-else class="text-gray-300 flex flex-col items-center">
          <svg class="w-24 h-24 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg>
          <span class="text-lg">無圖片預覽</span>
        </div>
      </div>

      <div class="p-8 flex flex-col">
        <div class="flex items-center justify-between mb-4">
          <span class="bg-blue-100 text-blue-800 text-sm font-bold px-3 py-1 rounded-full">
            {{ product.category }}
          </span>
          <span class="text-xs text-gray-400">更新於: {{ formatDate(product.last_updated) }}</span>
        </div>

        <h1 class="text-2xl font-bold text-gray-900 leading-tight mb-6">
          {{ product.name }}
        </h1>

        <div class="mb-8 space-y-3">
          <div v-for="(tip, index) in smartTips" :key="index" 
            class="p-4 rounded-lg border-l-4 flex items-start gap-3"
            :class="tip.type === 'warning' ? 'bg-amber-50 border-amber-500 text-amber-800' : 'bg-blue-50 border-blue-500 text-blue-800'">
            <div class="mt-0.5 text-lg">
              <span v-if="tip.type === 'warning'">⚠️</span>
              <span v-else>💡</span>
            </div>
            <div>
              <h4 class="font-bold text-sm">{{ tip.title }}</h4>
              <p class="text-sm mt-1 opacity-90 leading-relaxed">{{ tip.msg.replace(/\*\*/g, '') }}</p>
            </div>
          </div>
        </div>

        <div class="bg-gray-50 rounded-lg p-4 mb-8">
          <h3 class="text-sm font-bold text-gray-500 uppercase tracking-wider mb-3">詳細規格</h3>
          <div class="grid grid-cols-2 gap-y-2 gap-x-4 text-sm">
            <template v-if="product.specs && Object.keys(product.specs).length">
              <div v-for="(val, key) in product.specs" :key="key" class="flex flex-col">
                <span class="text-gray-400 text-xs">{{ key }}</span>
                <span class="font-medium text-gray-800">{{ val }}</span>
              </div>
            </template>
            <span v-else class="text-gray-400 italic">尚無詳細規格參數</span>
          </div>
        </div>

        <div class="mt-auto border-t border-gray-100 pt-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div>
            <span class="block text-xs text-gray-400">此通路最新紀錄價格</span>
            <span class="text-3xl font-extrabold text-red-600">
              ${{ (product.latest_price || product.price || 0).toLocaleString() }}
            </span>
          </div>
          
          <button 
            @click="goToStore"
            class="w-full sm:w-auto bg-gray-900 hover:bg-black text-white px-8 py-4 rounded-xl font-bold text-lg shadow-lg hover:shadow-xl transition-all transform hover:-translate-y-0.5 flex items-center justify-center gap-2">
            前往{{ product.source === 'coolpc' ? '原價屋估價頁' : 'PChome 購買' }}
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path d="M11 3a1 1 0 100 2h2.586l-6.293 6.293a1 1 0 101.414 1.414L15 6.414V9a1 1 0 102 0V4a1 1 0 00-1-1h-5z" />
              <path d="M5 5a2 2 0 00-2 2v8a2 2 0 002 2h8a2 2 0 002-2v-3a1 1 0 10-2 0v3H5V7h3a1 1 0 000-2H5z" />
            </svg>
          </button>
        </div>

      </div>
    </div>
    <section class="border-t border-gray-200 p-6 md:p-8" aria-live="polite">
      <h2 class="text-xl font-bold text-gray-900">跨通路比價</h2>
      <p class="mt-2 text-sm text-gray-500">比較 {{ otherStore }} 已收錄的相同型號，價格以各通路最後同步紀錄為準。</p>
      <p v-if="loading" class="mt-4 text-gray-500">正在比對商品…</p>
      <div v-else-if="error" class="mt-4 text-red-700">
        {{ error }} <button class="underline ml-2" @click="emit('retry')">重新載入</button>
      </div>
      <div v-else-if="product.comparisons?.length" class="mt-5 space-y-4">
        <article v-for="offer in product.comparisons" :key="offer.id" class="rounded-xl border border-gray-200 p-4 sm:flex sm:items-center sm:justify-between gap-4">
          <div>
            <span class="text-sm font-bold">{{ offer.source === 'coolpc' ? '原價屋' : 'PChome' }}</span>
            <span class="ml-2 rounded bg-blue-50 px-2 py-1 text-xs text-blue-800">{{ offer.channel }}</span>
            <h3 class="mt-3 font-medium text-gray-900">{{ offer.name }}</h3>
            <p class="mt-1 text-xs text-gray-500">更新於 {{ formatDate(offer.last_updated) }}</p>
            <p class="mt-1 text-xs text-gray-500">{{ offer.match_note }}</p>
          </div>
          <div class="mt-4 sm:mt-0 shrink-0">
            <p class="text-xl font-bold text-red-600">NT$ {{ offer.latest_price.toLocaleString() }}</p>
            <p class="mt-1 text-sm text-gray-600">{{ priceDifference(offer.latest_price) }}</p>
            <div class="mt-3 flex gap-3 text-sm text-blue-700">
              <button class="underline" @click="emit('open', offer)">查看詳情</button>
              <a class="underline" :href="storeUrl(offer)" target="_blank" rel="noopener noreferrer">前往通路</a>
            </div>
          </div>
        </article>
      </div>
      <p v-else class="mt-4 rounded-lg bg-gray-50 p-4 text-gray-600">目前未找到 {{ otherStore }} 可確認相同型號與規格的商品。</p>
      <p class="mt-4 text-xs text-gray-500">原價屋標示為實體通路估價參考；實際售價、庫存、搭購條件及保固請向店家確認。</p>
    </section>
  </div>
</template>
