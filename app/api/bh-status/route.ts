import { NextResponse } from 'next/server'
import fs from 'node:fs/promises'
import path from 'node:path'
import { spawn } from 'node:child_process'

/**
 * B&H Enhancement 看盘 API.
 *
 * 数据源: scripts/bh_status.py 写出的 deliverables/bh_enhancement/bh_status.json
 *
 * 设计:
 *  - GET /api/bh-status          -> 返回完整状态 JSON (summary + results)
 *  - GET /api/bh-status?refresh=1 -> 触发 Python 重算后再返回 (同步等待, ~5s)
 *  - force-dynamic + no-store: 每次都读最新文件
 */
const DATA_DIR =
  process.env.DELIVERABLES_DIR || path.join(process.cwd(), 'deliverables')
const DATA_FILE = path.join(DATA_DIR, 'bh_enhancement', 'bh_status.json')
const SCRIPT = path.join(process.cwd(), 'scripts', 'bh_status.py')
const PY = path.join(process.cwd(), '.venv', 'bin', 'python')

export const dynamic = 'force-dynamic'
export const revalidate = 0
export const maxDuration = 60

let cache: { mtime: number; data: any } | null = null

async function loadFile(): Promise<{ mtime: number; data: any }> {
  const stat = await fs.stat(DATA_FILE)
  if (cache && cache.mtime === stat.mtimeMs) return cache
  const raw = await fs.readFile(DATA_FILE, 'utf-8')
  const data = JSON.parse(raw)
  cache = { mtime: stat.mtimeMs, data }
  return cache
}

/** 触发 Python 脚本重新生成状态 JSON. */
async function refresh(): Promise<{ ok: boolean; error?: string }> {
  return new Promise((resolve) => {
    const p = spawn(PY, [SCRIPT], {
      cwd: process.cwd(),
      stdio: ['ignore', 'pipe', 'pipe'],
    })
    let stderr = ''
    p.stderr.on('data', (d) => {
      stderr += d.toString()
    })
    p.on('close', (code) => {
      if (code === 0) {
        // 失效缓存, 下次 loadFile 会重读
        cache = null
        resolve({ ok: true })
      } else {
        resolve({ ok: false, error: stderr.slice(-500) || `exit ${code}` })
      }
    })
    p.on('error', (err) => resolve({ ok: false, error: err.message }))
  })
}

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url)
  const wantRefresh = searchParams.get('refresh') === '1'

  if (wantRefresh) {
    const r = await refresh()
    if (!r.ok) {
      return NextResponse.json(
        { message: `刷新失败: ${r.error}` },
        { status: 500 },
      )
    }
  }

  try {
    const { data } = await loadFile()
    return NextResponse.json(data, {
      headers: { 'Cache-Control': 'no-store, max-age=0' },
    })
  } catch {
    return NextResponse.json(
      {
        message:
          '状态数据未生成。请先访问 /api/bh-status?refresh=1 触发计算, 或运行: python3 scripts/bh_status.py',
      },
      { status: 503 },
    )
  }
}
