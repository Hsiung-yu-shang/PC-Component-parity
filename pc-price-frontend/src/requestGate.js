// Each view accepts only its most recent response, even if a server ignores abort.
export function createRequestGate() {
  let current = null
  return {
    begin() {
      current?.abort()
      const controller = new AbortController()
      current = controller
      return { signal: controller.signal, isCurrent: () => current === controller && !controller.signal.aborted }
    },
    cancel() { current?.abort(); current = null },
  }
}

export function productPageUrl(value, origin) {
  const url = new URL(value, origin)
  if (url.pathname !== '/api/products/') throw new Error('分頁網址格式不正確。')
  return url.pathname + url.search
}
