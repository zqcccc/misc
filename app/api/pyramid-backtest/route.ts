import { NextResponse } from 'next/server'
import fs from 'node:fs/promises'
import path from 'node:path'

/**
 * 金字塔加仓/减仓策略回测数据出口。
 * 数据真源: scripts/pyramid_backtest.py 写出的 deliverables/pyramid_backtest/result.json
 *
 * GET /api/pyramid-backtest              -> 完整结果(含 nav 曲线)，默认返回 default_version
 * GET /api/pyramid-backtest?version=v1   -> 指定版本
 * GET /api/pyramid-backtest?overview=1   -> 轻量概览(剔除 nav/position/trades)，含两个版本
 */
const DATA_DIR = process.env.DELIVERABLES_DIR || path.join(process.cwd(), 'deliverables')
const DATA_FILE = path.join(DATA_DIR, 'pyramid_backtest', 'result.json')

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
  const overviewOnly = searchParams.get('overview')
  const version = searchParams.get('version')

  let all: any
  try {
    all = await loadAll()
  } catch {
    return NextResponse.json(
      { message: '回测数据未生成。请先运行: python3 scripts/pyramid_backtest.py' },
      { status: 503 },
    )
  }

  const headers = {
    'Cache-Control': 'no-store, max-age=0',
  }

  if (overviewOnly) {
    const versions: Record<string, any> = {}
    for (const [key, val] of Object.entries(all.versions ?? {})) {
      const v: any = val
      versions[key] = {
        label: v.label,
        params: v.params,
        n_assets: v.n_assets,
        n_win: v.n_win,
        win_rate: v.win_rate,
        n_cagr_win: v.n_cagr_win,
        n_mdd_win: v.n_mdd_win,
        avg_delta_cagr: v.avg_delta_cagr,
        avg_delta_mdd: v.avg_delta_mdd,
        results: (v.results ?? []).map((r: any) => ({
          ticker: r.ticker,
          group: r.group,
          strat: r.strat,
          bh: r.bh,
          n_trades: r.n_trades,
          delta_cagr: r.delta_cagr,
          delta_mdd: r.delta_mdd,
          win: r.win,
        })),
      }
    }
    return NextResponse.json(
      {
        strategy: all.strategy,
        default_version: all.default_version,
        versions,
      },
      { headers },
    )
  }

  const ver = version || all.default_version || 'v2'
  const verData = all.versions?.[ver]
  if (!verData) {
    return NextResponse.json(
      { message: `版本不存在: ${ver}` },
      { status: 404, headers },
    )
  }

  return NextResponse.json(
    {
      strategy: all.strategy,
      default_version: all.default_version,
      current_version: ver,
      available_versions: Object.keys(all.versions ?? {}),
      ...verData,
    },
    { headers },
  )
}
