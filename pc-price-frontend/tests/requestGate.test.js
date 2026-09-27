import test from 'node:test'
import assert from 'node:assert/strict'
import { createRequestGate, productPageUrl } from '../src/requestGate.js'
import { storeUrl } from '../src/storeUrl.js'

test('late responses cannot replace the current product or list', () => {
  const gate = createRequestGate()
  const slow = gate.begin()
  const fast = gate.begin()
  assert.equal(slow.signal.aborted, true)
  assert.equal(slow.isCurrent(), false)
  assert.equal(fast.isCurrent(), true)
  gate.cancel()
  assert.equal(fast.isCurrent(), false)
})

test('pagination always uses this site and rejects non-product paths', () => {
  assert.equal(productPageUrl('http://internal:8000/api/products/?page=2&source=coolpc', 'https://site.test'), '/api/products/?page=2&source=coolpc')
  assert.throws(() => productPageUrl('https://evil.test/admin/', 'https://site.test'))
})

test('unregistered sources cannot create outbound purchase links', () => {
  assert.equal(storeUrl({ source: 'unknown', product_url: 'https://evil.test' }), '')
})
