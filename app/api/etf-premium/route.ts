import { NextResponse } from 'next/server'
import { groupCounts } from '@/lib/etf-premium'
import { UpstreamError, getSnapshot } from './upstream'

export const dynamic = 'force-dynamic'

/**
 * GET /api/etf-premium
 * 全量跨境 ETF 溢价快照。`?refresh=1` 跳过 60 秒进程内缓存手动刷新。
 */
export async function GET(request: Request) {
  const url = new URL(request.url)
  const refresh = url.searchParams.get('refresh') === '1'
  try {
    const snapshot = await getSnapshot(refresh)
    const rows = snapshot.rows
    const premiumCount = rows.filter((row) => row.premiumPct != null).length
    const missingIopv = rows.filter((row) => row.iopv == null).length
    const latestQuoteDate = rows
      .map((row) => row.quoteDate)
      .filter((date): date is string => date != null)
      .sort()
      .pop() ?? null
    const serialized = rows.map((row) => ({
      ...row,
      isStaleQuote: latestQuoteDate != null && row.quoteDate != null && row.quoteDate !== latestQuoteDate,
    }))
    return NextResponse.json({
      ok: true,
      generatedAt: snapshot.generatedAt,
      quoteSource: snapshot.quoteSource,
      quoteSourceNote: snapshot.quoteSourceNote,
      universe: {
        navDate: snapshot.universeNavDate,
        etfCount: snapshot.etfCount,
        excludedNonEtf: snapshot.excludedNonEtf,
        excludedOther: snapshot.excludedOther,
      },
      counts: {
        crossBorder: rows.length,
        qdii: rows.filter((row) => row.mechanism === 'qdii').length,
        connect: rows.filter((row) => row.mechanism === 'connect').length,
        withPremium: premiumCount,
        missingIopv,
        ungrouped: rows.filter((row) => row.indexKey == null).length,
      },
      groups: groupCounts(rows),
      latestQuoteDate,
      rows: serialized,
    })
  } catch (error) {
    if (error instanceof UpstreamError) {
      return NextResponse.json(
        { ok: false, stage: error.stage, message: error.message },
        { status: 502 },
      )
    }
    const message = error instanceof Error ? error.message : String(error)
    return NextResponse.json(
      { ok: false, stage: 'server', message: `溢价快照生成失败：${message}` },
      { status: 500 },
    )
  }
}
