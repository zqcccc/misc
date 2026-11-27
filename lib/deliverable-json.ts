import type { Stats } from 'node:fs'
import { readFile, stat } from 'node:fs/promises'
import * as path from 'node:path'

/**
 * Shared responder for API routes that serve a deliverable JSON file as
 * `{ success: true, data: <file> }`.
 *
 * Per request it only stats the file; the 200 body (the whole deliverable
 * spliced into the envelope, no JSON.parse/stringify round trip) is cached
 * in memory keyed by file path and validated against the file's
 * mtimeMs + size, so a same-mtime/different-size rewrite never serves a
 * stale hit. At most MAX_CACHE_ENTRIES files are cached.
 */

const STABLE_ERROR_MESSAGE = 'Failed to load strategy data'
const CACHE_CONTROL = 'public, max-age=0, must-revalidate'
const MAX_CACHE_ENTRIES = 8

interface DeliverableCacheEntry {
  mtimeMs: number
  size: number
  etag: string
  body: string
}

const cache = new Map<string, DeliverableCacheEntry>()

function etagFor(filePath: string, mtimeMs: number, size: number): string {
  const base = path.basename(filePath).replace(/[^a-zA-Z0-9._-]/g, '-')
  return `"${base}-${mtimeMs}-${size}"`
}

function store(key: string, entry: DeliverableCacheEntry): void {
  if (!cache.has(key) && cache.size >= MAX_CACHE_ENTRIES) {
    const oldest = cache.keys().next().value
    if (oldest !== undefined) {
      cache.delete(oldest)
    }
  }
  cache.set(key, entry)
}

function stableErrorResponse(): Response {
  return new Response(JSON.stringify({ success: false, error: STABLE_ERROR_MESSAGE }), {
    status: 500,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'no-store',
    },
  })
}

function ifNoneMatchSatisfies(request: Request, etag: string): boolean {
  const header = request.headers.get('if-none-match')
  if (!header) {
    return false
  }
  return header.split(',').some((candidate) => {
    const tag = candidate.trim()
    return tag === '*' || tag === etag || tag === `W/${etag}`
  })
}

function entryResponse(request: Request, entry: DeliverableCacheEntry): Response {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': CACHE_CONTROL,
    ETag: entry.etag,
  }
  if (ifNoneMatchSatisfies(request, entry.etag)) {
    return new Response(null, { status: 304, headers })
  }
  return new Response(entry.body, { status: 200, headers })
}

export async function deliverableJsonResponse(
  request: Request,
  filePath: string
): Promise<Response> {
  let before: Stats
  try {
    before = await stat(filePath)
  } catch (err) {
    console.error(`[deliverable-json] stat failed for ${filePath}:`, err)
    return stableErrorResponse()
  }
  if (!before.isFile()) {
    console.error(`[deliverable-json] not a regular file: ${filePath}`)
    return stableErrorResponse()
  }

  const cached = cache.get(filePath)
  if (cached && cached.mtimeMs === before.mtimeMs && cached.size === before.size) {
    return entryResponse(request, cached)
  }

  let raw: string
  try {
    raw = await readFile(filePath, 'utf-8')
  } catch (err) {
    console.error(`[deliverable-json] read failed for ${filePath}:`, err)
    return stableErrorResponse()
  }

  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch (err) {
    cache.delete(filePath)
    console.error(`[deliverable-json] invalid JSON in ${filePath}:`, err)
    return stableErrorResponse()
  }
  if (
    typeof parsed !== 'object' ||
    parsed === null ||
    Array.isArray(parsed)
  ) {
    cache.delete(filePath)
    console.error(`[deliverable-json] top-level JSON in ${filePath} is not an object`)
    return stableErrorResponse()
  }

  const entry: DeliverableCacheEntry = {
    mtimeMs: before.mtimeMs,
    size: before.size,
    etag: etagFor(filePath, before.mtimeMs, before.size),
    body: `{"success":true,"data":${raw}}`,
  }

  // Re-stat after reading: if the file changed underneath this read, the
  // fingerprint no longer describes the bytes we read, so serve them once
  // without caching. The next request re-reads and re-caches.
  try {
    const after = await stat(filePath)
    if (
      after.isFile() &&
      after.mtimeMs === before.mtimeMs &&
      after.size === before.size
    ) {
      store(filePath, entry)
    }
  } catch {
    // Unreadable at this instant: serve this read uncached.
  }

  return entryResponse(request, entry)
}
