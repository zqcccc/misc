import { PrismaClient } from '@prisma/client'
import { NextResponse } from 'next/server'
import { buildCompanyValuationCard } from './summary'
import {
  getCompanyValuationRedis,
  buildCompanyValuationCacheKey,
  buildCompanyValuationTotalKey,
  buildCompanyValuationAllKey,
  readCompanyValuationCache,
  writeCompanyValuationCache,
} from './cache'

const prisma = new PrismaClient()
const PAGE_SIZE = 30

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

async function getAllSortedEntries(): Promise<ReturnType<typeof buildCompanyValuationCard>[]> {
  const redis = await getCompanyValuationRedis()
  const cacheKey = buildCompanyValuationAllKey()

  const cached = await readCompanyValuationCache<{ entries: ReturnType<typeof buildCompanyValuationCard>[] }>(redis, cacheKey)
  if (cached) {
    return cached.entries
  }

  const companies = await prisma.company.findMany({
    where: { visible: true },
    include: companyInclude,
  })

  const cards = companies.map((company) =>
    buildCompanyValuationCard({
      company,
      latestValuation: company.valuations[0] || null,
      latestExploration: company.explorations[0] || null,
      explanations: company.explanations,
    }),
  )

  const sortedCards = cards.sort((a, b) => {
    const qualityOrder = { '正常': 0, '待确认': 1, '需调整': 2 }
    const qualityDiff = qualityOrder[a.profitQuality] - qualityOrder[b.profitQuality]
    if (qualityDiff !== 0) return qualityDiff
    return (b.exploration.score ?? 0) - (a.exploration.score ?? 0)
  })

  await writeCompanyValuationCache(redis, cacheKey, { entries: sortedCards })
  return sortedCards
}

function filterEntries(
  entries: ReturnType<typeof buildCompanyValuationCard>[],
  search?: string,
  quality?: string,
) {
  let result = entries

  if (quality && quality !== '全部') {
    result = result.filter((e) => e.profitQuality === quality)
  }

  if (search && search.trim()) {
    const query = search.toLowerCase().trim()
    result = result.filter((e) => {
      const matchTitle = e.title.toLowerCase().includes(query)
      const matchSymbol = e.symbol.toLowerCase().includes(query)
      const matchTags = e.tags.some((tag) => tag.toLowerCase().includes(query))
      return matchTitle || matchSymbol || matchTags
    })
  }

  return result
}

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url)
    const pageParam = searchParams.get('page')
    const page = pageParam ? Math.max(1, parseInt(pageParam, 10) || 1) : 1
    const search = searchParams.get('search') || undefined
    const quality = searchParams.get('quality') || undefined

    const allEntries = await getAllSortedEntries()
    const filtered = filterEntries(allEntries, search, quality)

    const start = (page - 1) * PAGE_SIZE
    const end = start + PAGE_SIZE
    const pageEntries = filtered.slice(start, end)

    return NextResponse.json({
      entries: pageEntries,
      total: filtered.length,
      page,
      pageSize: PAGE_SIZE,
      hasMore: end < filtered.length,
    })
  } catch (error) {
    console.error('[company-valuation] load failed:', error)
    return NextResponse.json(
      { message: '公司估值数据获取失败' },
      { status: 500 },
    )
  }
}
