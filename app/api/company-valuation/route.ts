import { PrismaClient } from '@prisma/client'
import { NextResponse } from 'next/server'
import { buildCompanyValuationCard } from './summary'
import {
  getCompanyValuationRedis,
  buildCompanyValuationCacheKey,
  buildCompanyValuationTotalKey,
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

async function getTotalCount(): Promise<number> {
  const redis = await getCompanyValuationRedis()
  const totalKey = buildCompanyValuationTotalKey()

  const cachedTotal = await readCompanyValuationCache<number>(redis, totalKey)
  if (cachedTotal !== null) {
    return cachedTotal
  }

  const count = await prisma.companyPageEntry.count({
    where: { visible: true },
  })

  await writeCompanyValuationCache(redis, totalKey, count)
  return count
}

async function getAllSortedEntries(): Promise<ReturnType<typeof buildCompanyValuationCard>[]> {
  const redis = await getCompanyValuationRedis()
  const cacheKey = buildCompanyValuationCacheKey(0, PAGE_SIZE)

  const cached = await readCompanyValuationCache<{ entries: ReturnType<typeof buildCompanyValuationCard>[] }>(redis, cacheKey)
  if (cached) {
    return cached.entries
  }

  const entries = await prisma.companyPageEntry.findMany({
    where: { visible: true },
    include: {
      company: {
        include: companyInclude,
      },
    },
  })

  const cards = entries.map((entry) =>
    buildCompanyValuationCard({
      company: entry.company,
      entry,
      latestValuation: entry.company.valuations[0] || null,
      latestExploration: entry.company.explorations[0] || null,
      explanations: entry.company.explanations,
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

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url)
    const pageParam = searchParams.get('page')
    const page = pageParam ? Math.max(1, parseInt(pageParam, 10) || 1) : 1

    const [allEntries, total] = await Promise.all([
      getAllSortedEntries(),
      getTotalCount(),
    ])

    const start = (page - 1) * PAGE_SIZE
    const end = start + PAGE_SIZE
    const pageEntries = allEntries.slice(start, end)

    return NextResponse.json({
      entries: pageEntries,
      total,
      page,
      pageSize: PAGE_SIZE,
      hasMore: end < total,
    })
  } catch (error) {
    console.error('[company-valuation] load failed:', error)
    return NextResponse.json(
      { message: '公司估值数据获取失败' },
      { status: 500 },
    )
  }
}
