import { NextResponse } from 'next/server'
import fs from 'node:fs/promises'
import path from 'node:path'

/**
 * TRHRP 多市场回测数据的 HTTP 出口。
 *
 * 数据真源: scripts/trhrp_backtest_live.py 写出的 deliverables/trhrp_backtest_all/_all.json
 * (22 个标的, 每个含 meta/params/summary/timeseries)。
 *
 * 设计:
 *  - GET /api/trhrp-backtest               -> 轻量概览(不含 timeseries), 供列表/卡片/汇总表轮询
 *  - GET /api/trhrp-backtest?market=<label> -> 单标的完整结果(含 timeseries), 供图表按需加载
 *  - force-dynamic + no-store: 让页面每次轮询都拿到最新生成的文件
 *  - 模块内按文件 mtime 做内存缓存, 避免每个请求都解析 5MB JSON
 */
const DATA_DIR = process.env.DELIVERABLES_DIR || path.join(process.cwd(), 'deliverables')
const DATA_FILE = path.join(
  DATA_DIR,
  'trhrp_backtest_all',
  '_all.json',
)

export const dynamic = 'force-dynamic'
export const revalidate = 0

let cache: { mtime: number; data: any } | null = null

async function loadAll() {
  const stat = await fs.stat(DATA_FILE)
  if (cache && cache.mtime === stat.mtimeMs) return cache.data
  const raw = await fs.readFile(DATA_FILE, 'utf-8')
  const data = JSON.parse(raw)
  cache = { mtime: stat.mtimeMs, data }
  return data
}

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url)
  const market = searchParams.get('market')

  let all: any
  try {
    all = await loadAll()
  } catch {
    return NextResponse.json(
      {
        message:
          '回测数据未生成。请先运行: python3 scripts/trhrp_backtest_live.py',
      },
      { status: 503 },
    )
  }

  const headers = {
    'Cache-Control': 'no-store, max-age=0',
    'x-generated-at': all.generated_at ?? '',
  }

  // 单标的完整结果(含 timeseries)
  if (market) {
    const res = (all.results ?? []).find(
      (r: any) => r.meta?.label === market,
    )
    if (!res) {
      return NextResponse.json(
        { message: `未找到标的: ${market}` },
        { status: 404, headers },
      )
    }
    return NextResponse.json(res, { headers })
  }

  // 轻量概览(剔除 timeseries, 体积从 ~5MB 降到 ~30KB)
  const overview = {
    generated_at: all.generated_at,
    source: all.source,
    regime_cn: all.regime_cn,
    markets: all.markets ?? [],
  }
  return NextResponse.json(overview, { headers })
}
