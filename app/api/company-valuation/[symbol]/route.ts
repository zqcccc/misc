import { PrismaClient } from '@prisma/client'
import { NextResponse } from 'next/server'
import { normalizeMarketSymbol } from '../../profit-line/market-data'
import { buildCompanyValuationCard } from '../summary'

const prisma = new PrismaClient()

function canonicalCompanySymbol(input: string) {
  const normalized = normalizeMarketSymbol(input)
  if (normalized.market === 'hk') {
    return {
      market: normalized.market,
      symbol: `${normalized.symbol}.HK`,
    }
  }
  if (normalized.market === 'cn') {
    return {
      market: normalized.market,
      symbol: normalized.eastmoneyCode,
    }
  }
  return {
    market: normalized.market,
    symbol: normalized.symbol,
  }
}

function canonicalCompanySymbolVariants(input: string) {
  const normalized = normalizeMarketSymbol(input)
  if (normalized.market === 'hk') {
    const hkSymbol = `${normalized.symbol}.HK`
    return [
      { market: normalized.market, symbol: hkSymbol },
      { market: normalized.market, symbol: normalized.symbol },
    ]
  }
  if (normalized.market === 'cn') {
    return [
      { market: normalized.market, symbol: normalized.eastmoneyCode },
      { market: normalized.market, symbol: normalized.symbol },
    ]
  }
  return [{ market: normalized.market, symbol: normalized.symbol }]
}

const companyInclude = {
  valuations: {
    orderBy: [{ asOfDate: 'desc' as const }, { createdAt: 'desc' as const }],
    take: 1,
  },
  explorations: {
    where: { visibility: 'published' },
    orderBy: [{ pinned: 'desc' as const }, { createdAt: 'desc' as const }],
    take: 1,
  },
  explanations: {
    where: { isCurrent: true },
    orderBy: [{ asOfDate: 'desc' as const }, { createdAt: 'desc' as const }],
    take: 8,
  },
}

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ symbol: string }> },
) {
  const { symbol } = await params
  const cleanSymbol = symbol?.trim()
  if (!cleanSymbol) {
    return NextResponse.json(
      { message: '缺少 symbol 参数' },
      { status: 400 },
    )
  }

  const symbolVariants = canonicalCompanySymbolVariants(cleanSymbol)

  try {
    let company = null
    for (const variant of symbolVariants) {
      company = await prisma.company.findUnique({
        where: {
          market_symbol: variant,
        },
        include: companyInclude,
      })
      if (company) break
    }

    if (!company) {
      return NextResponse.json(
        { message: `未找到公司 ${cleanSymbol}` },
        { status: 404 },
      )
    }

    const card = buildCompanyValuationCard({
      company,
      latestValuation: company.valuations[0] || null,
      latestExploration: company.explorations[0] || null,
      explanations: company.explanations,
    })

    return NextResponse.json({ current: card })
  } catch (error) {
    console.error('[company-valuation/symbol] load failed:', error)
    return NextResponse.json(
      { message: '公司估值数据获取失败' },
      { status: 500 },
    )
  }
}
