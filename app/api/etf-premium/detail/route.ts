import { NextResponse } from 'next/server'
import { UpstreamError, getDetail, peekSnapshot } from '../upstream'
export const dynamic = 'force-dynamic'

const DEFAULT_DAYS = 180
const MIN_DAYS = 30
const MAX_DAYS = 730

function clampDays(raw: string | null): number {
  const value = Number(raw)
  if (!Number.isFinite(value)) return DEFAULT_DAYS
  return Math.min(MAX_DAYS, Math.max(MIN_DAYS, Math.round(value)))
}

/**
 * GET /api/etf-premium/detail?code=513500&days=180
 * 单只跨境 ETF 的「收盘价 × 当日单位净值」日频溢价序列。
 * 机制/名称优先取快照里的已核对行；快照失败时退回基金档案自身字段。
 */
export async function GET(request: Request) {
  const url = new URL(request.url)
  const code = (url.searchParams.get('code') ?? '').trim()
  const days = clampDays(url.searchParams.get('days'))
  if (!/^\d{6}$/.test(code)) {
    return NextResponse.json(
      { ok: false, stage: 'input', message: '缺少或非法的 code 参数' },
      { status: 400 },
    )
  }
  const row = peekSnapshot()?.rows.find((item) => item.code === code)
  const hint: { name: string | null; mechanism: 'qdii' | 'connect' | null } | null = row
    ? { name: row.name, mechanism: row.mechanism }
    : null
  try {
    const detail = await getDetail(code, days, hint ?? undefined)
    return NextResponse.json({ ok: true, days, ...detail })
  } catch (error) {
    if (error instanceof UpstreamError) {
      return NextResponse.json(
        { ok: false, stage: error.stage, message: error.message },
        { status: 502 },
      )
    }
    const message = error instanceof Error ? error.message : String(error)
    return NextResponse.json(
      { ok: false, stage: 'server', message: `历史溢价序列生成失败：${message}` },
      { status: 500 },
    )
  }
}
