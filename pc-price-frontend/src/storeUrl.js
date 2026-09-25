export function storeUrl(product) {
  const fallback = product.source === 'coolpc'
    ? 'https://www.coolpc.com.tw/evaluate.php'
    : `https://24h.pchome.com.tw/prod/${encodeURIComponent(product.id)}`
  try {
    const url = new URL(product.product_url || fallback)
    const host = product.source === 'coolpc' ? 'www.coolpc.com.tw' : '24h.pchome.com.tw'
    return url.protocol === 'https:' && url.hostname === host && !url.username && !url.password && !url.port
      ? url.href : fallback
  } catch {
    return fallback
  }
}
