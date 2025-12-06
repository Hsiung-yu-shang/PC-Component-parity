<script setup>
import { computed } from 'vue'

// 接收父層傳來的商品資料
const props = defineProps({
  product: {
    type: Object,
    required: true
  }
})

// 定義「返回」事件，通知父層切換回列表
const emit = defineEmits(['back'])

// 格式化日期
const formatDate = (dateString) => {
  if (!dateString) return ''
  return new Date(dateString).toLocaleDateString('zh-TW')
}

// 前往 PChome
const goToPChome = () => {
  const url = `https://24h.pchome.com.tw/prod/${props.product.id}`
  window.open(url, '_blank')
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
      <span class="text-xs text-gray-400">PChome ID: {{ product.id }}</span>
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
              <p class="text-sm mt-1 opacity-90 leading-relaxed" v-html="tip.msg.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>')"></p>
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
            <span class="block text-xs text-gray-400">目前最低價格</span>
            <span class="text-3xl font-extrabold text-red-600">
              ${{ (product.latest_price || product.price || 0).toLocaleString() }}
            </span>
          </div>
          
          <button 
            @click="goToPChome"
            class="w-full sm:w-auto bg-gray-900 hover:bg-black text-white px-8 py-4 rounded-xl font-bold text-lg shadow-lg hover:shadow-xl transition-all transform hover:-translate-y-0.5 flex items-center justify-center gap-2">
            前往 PChome 購買
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path d="M11 3a1 1 0 100 2h2.586l-6.293 6.293a1 1 0 101.414 1.414L15 6.414V9a1 1 0 102 0V4a1 1 0 00-1-1h-5z" />
              <path d="M5 5a2 2 0 00-2 2v8a2 2 0 002 2h8a2 2 0 002-2v-3a1 1 0 10-2 0v3H5V7h3a1 1 0 000-2H5z" />
            </svg>
          </button>
        </div>

      </div>
    </div>
  </div>
</template>