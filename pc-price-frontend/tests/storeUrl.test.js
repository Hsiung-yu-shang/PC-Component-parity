import test from 'node:test'
import assert from 'node:assert/strict'
import { storeUrl } from '../src/storeUrl.js'

test('external store links reject scripts, other hosts, userinfo and ports', () => {
  for (const url of ['javascript:alert(1)', 'https://evil.test', 'https://24h.pchome.com.tw.evil.test/', 'https://user@24h.pchome.com.tw/', 'https://24h.pchome.com.tw:1234/', 'http://24h.pchome.com.tw/']) {
    assert.equal(storeUrl({ id: 'a', source: 'pchome', product_url: url }), 'https://24h.pchome.com.tw/prod/a')
  }
})
test('valid source URLs and fallbacks', () => {
  assert.equal(storeUrl({ source: 'coolpc' }), 'https://www.coolpc.com.tw/evaluate.php')
  assert.equal(storeUrl({ source: 'pchome', id: 'a/b' }), 'https://24h.pchome.com.tw/prod/a%2Fb')
  assert.equal(storeUrl({ source: 'pchome', product_url: 'https://24h.pchome.com.tw/prod/ABC' }), 'https://24h.pchome.com.tw/prod/ABC')
  assert.equal(storeUrl({ source: 'coolpc', product_url: 'https://24h.pchome.com.tw/prod/ABC' }), 'https://www.coolpc.com.tw/evaluate.php')
})
