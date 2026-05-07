import { PrismaClient } from '@prisma/client'
import { NextResponse } from 'next/server'
import { normalizeMarketSymbol } from '../profit-line/market-data'
import { buildCompanyValuationCard } from './summary'

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

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const symbol = searchParams.get('symbol')?.trim()
  const currentSymbol = symbol ? canonicalCompanySymbol(symbol) : null

  try {
    const [entries, currentCompany] = await Promise.all([
      prisma.companyPageEntry.findMany({
        where: { visible: true },
        orderBy: [{ sortOrder: 'asc' }, { createdAt: 'desc' }],
        take: 30,
        include: {
          company: {
            include: companyInclude,
          },
        },
      }),
      currentSymbol
        ? prisma.company.findUnique({
            where: {
              market_symbol: currentSymbol,
            },
            include: companyInclude,
          })
        : Promise.resolve(null),
    ])

    const cards = entries.map((entry) =>
      buildCompanyValuationCard({
        company: entry.company,
        entry,
        latestValuation: entry.company.valuations[0] || null,
        latestExploration: entry.company.explorations[0] || null,
        explanations: entry.company.explanations,
      }),
    )
    const current = currentCompany
      ? buildCompanyValuationCard({
          company: currentCompany,
          latestValuation: currentCompany.valuations[0] || null,
          latestExploration: currentCompany.explorations[0] || null,
          explanations: currentCompany.explanations,
        })
      : cards.find(
          (entry) =>
            currentSymbol &&
            entry.market === currentSymbol.market &&
            entry.symbol === currentSymbol.symbol,
        ) || null

    return NextResponse.json({
      entries: cards,
      current,
    })
  } catch (error) {
    console.error('[company-valuation] load failed:', error)
    return NextResponse.json(
      { message: '公司估值数据获取失败' },
      { status: 500 },
    )
  }
}
