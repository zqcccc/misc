import * as assert from 'node:assert/strict'
import * as fs from 'node:fs/promises'
import * as path from 'node:path'
import { deliverableJsonResponse } from '../lib/deliverable-json'

const STABLE_ERROR = 'Failed to load strategy data'
const FIXED_MTIME = new Date(1700000000000)
const LATER_MTIME = new Date(1700000005000)

function get(filePath: string): Promise<Response> {
  return deliverableJsonResponse(new Request('http://localhost/api/test'), filePath)
}

function assertNoStaleLeak(body: string, staleMarker: string, filePath: string): void {
  assert.ok(!body.includes(staleMarker), `must not leak stale content: ${staleMarker}`)
  assert.ok(!body.includes(filePath), 'error body must not contain the file path')
  assert.ok(!body.includes('Unexpected'), 'error body must not contain err.message')
}

async function run() {
  const tempRoot = path.resolve('temp')
  await fs.mkdir(tempRoot, { recursive: true })
  const dir = await fs.mkdtemp(path.join(tempRoot, 'deliverable-json-'))
  const file = path.join(dir, 'strategy.json')

  // 缺失文件：稳定 500，不外露路径或 err.message
  let res = await get(file)
  assert.equal(res.status, 500)
  assert.equal(res.headers.get('cache-control'), 'no-store')
  let body = await res.text()
  let json = JSON.parse(body)
  assert.equal(json.success, false)
  assert.equal(json.error, STABLE_ERROR)
  assertNoStaleLeak(body, '{"a"', file)

  // 新文件读取：200 + 字节级 envelope + ETag/Cache-Control
  const v1 = '{"a":1,"nested":{"b":2}}'
  await fs.writeFile(file, v1)
  await fs.utimes(file, FIXED_MTIME, FIXED_MTIME)
  res = await get(file)
  assert.equal(res.status, 200)
  assert.equal(res.headers.get('cache-control'), 'public, max-age=0, must-revalidate')
  body = await res.text()
  assert.equal(body, `{"success":true,"data":${v1}}`)
  json = JSON.parse(body)
  assert.deepEqual(json, { success: true, data: { a: 1, nested: { b: 2 } } })
  const etagV1 = res.headers.get('etag')
  assert.ok(etagV1)

  // 缓存命中：同一指纹再请求，返回相同内容
  res = await get(file)
  assert.equal(res.status, 200)
  assert.equal(await res.text(), `{"success":true,"data":${v1}}`)
  assert.equal(res.headers.get('etag'), etagV1)

  // If-None-Match 命中：304 空响应体
  res = await deliverableJsonResponse(
    new Request('http://localhost/api/test', { headers: { 'if-none-match': etagV1 } }),
    file
  )
  assert.equal(res.status, 304)
  assert.equal(await res.text(), '')
  assert.equal(res.headers.get('etag'), etagV1)
  // 弱化前缀同样命中
  res = await deliverableJsonResponse(
    new Request('http://localhost/api/test', {
      headers: { 'if-none-match': `W/${etagV1}` },
    }),
    file
  )
  assert.equal(res.status, 304)

  // mtime 相同但 size 不同：不得命中陈旧缓存，重新读取新内容
  const v2 = '{"a":7,"nested":{"b":22}}'
  await fs.writeFile(file, v2)
  await fs.utimes(file, FIXED_MTIME, FIXED_MTIME)
  res = await get(file)
  assert.equal(res.status, 200)
  json = JSON.parse(await res.text())
  assert.deepEqual(json, { success: true, data: { a: 7, nested: { b: 22 } } })
  const etagV2 = res.headers.get('etag')
  assert.ok(etagV2 && etagV1 && etagV2 !== etagV1)

  // 旧 etag 的条件请求：返回 200 全量而不是 304
  res = await deliverableJsonResponse(
    new Request('http://localhost/api/test', { headers: { 'if-none-match': etagV1 } }),
    file
  )
  assert.equal(res.status, 200)
  assert.equal(await res.text(), `{"success":true,"data":${v2}}`)

  // mtime 变化但 size 相同：同样重新读取
  const v3 = '{"a":9,"nested":{"b":22}}'
  await fs.writeFile(file, v3)
  await fs.utimes(file, LATER_MTIME, LATER_MTIME)
  res = await get(file)
  assert.equal(res.status, 200)
  json = JSON.parse(await res.text())
  assert.deepEqual(json, { success: true, data: { a: 9, nested: { b: 22 } } })
  const etagV3 = res.headers.get('etag')
  assert.ok(etagV3 && etagV2 && etagV3 !== etagV2)

  // 损坏 JSON：不返回旧缓存，稳定 500；连续请求也保持 500
  await fs.writeFile(file, '{oops')
  res = await get(file)
  body = await res.text()
  assert.equal(res.status, 500)
  json = JSON.parse(body)
  assert.equal(json.success, false)
  assert.equal(json.error, STABLE_ERROR)
  assertNoStaleLeak(body, '"a":9', file)
  res = await get(file)
  assert.equal(res.status, 500)
  assert.equal(JSON.parse(await res.text()).error, STABLE_ERROR)

  // 顶层非对象：数组、null 都是 500
  for (const invalid of ['[1,2]', 'null']) {
    await fs.writeFile(file, invalid)
    res = await get(file)
    assert.equal(res.status, 500)
    body = await res.text()
    assert.equal(JSON.parse(body).error, STABLE_ERROR)
    assertNoStaleLeak(body, '"a":', file)
  }

  // 修复后恢复 200 并给出新内容
  const v4 = '{"a":10,"nested":{"b":22}}'
  await fs.writeFile(file, v4)
  res = await get(file)
  assert.equal(res.status, 200)
  json = JSON.parse(await res.text())
  assert.deepEqual(json, { success: true, data: { a: 10, nested: { b: 22 } } })

  await fs.rm(dir, { recursive: true, force: true })
}

run()
