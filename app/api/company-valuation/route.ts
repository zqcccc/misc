import { PrismaClient } from '@prisma/client'
import { NextResponse } from 'next/server'
import {
  companyValuationListCardFromSummary,
  companyValuationListSummarySelect,
} from './summary-store'
import { buildCompanyValuationCard } from './summary'
import {
  buildCompanyValuationSummaryOrderBy,
  buildCompanyValuationSummaryWhere,
  buildCompanyValuationWhere,
  companyInclude,
  companyValuationOrderBy,
} from './query'

const prisma = new PrismaClient()
const PAGE_SIZE = 30

async function getSearchPageEntries(search: string, page: number) {
  const where = buildCompanyValuationWhere(search)
  const start = (page - 1) * PAGE_SIZE

  const [total, companies] = await Promise.all([
    prisma.company.count({ where }),
    prisma.company.findMany({
      where,
      include: companyInclude,
      orderBy: companyValuationOrderBy,
      skip: start,
      take: PAGE_SIZE,
    }),
  ])

  const entries = companies.map((company) =>
    buildCompanyValuationCard({
      company,
      latestValuation: company.valuations[0] || null,
      latestExploration: company.explorations[0] || null,
      explanations: company.explanations,
    }),
  )

  return {
    entries,
    total,
    hasMore: start + entries.length < total,
  }
}

async function getAllSortedEntries() {
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

  return cards.sort((a, b) => {
    const qualityOrder = { 正常: 0, 待确认: 1, 需调整: 2 }
    const qualityDiff = qualityOrder[a.profitQuality] - qualityOrder[b.profitQuality]
    if (qualityDiff !== 0) return qualityDiff
    return (b.exploration.score ?? 0) - (a.exploration.score ?? 0)
  })
}

function filterEntries(
  entries: Awaited<ReturnType<typeof getAllSortedEntries>>,
  search?: string,
  quality?: string,
) {
  let result = entries

  if (quality && quality !== '全部') {
    result = result.filter((entry) => entry.profitQuality === quality)
  }

  if (search?.trim()) {
    const query = search.toLowerCase().trim()
    result = result.filter((entry) => {
      const matchTitle = entry.title.toLowerCase().includes(query)
      const matchSymbol = entry.symbol.toLowerCase().includes(query)
      const matchTags = entry.tags.some((tag) => tag.toLowerCase().includes(query))
      return matchTitle || matchSymbol || matchTags
    })
  }

  return result
}

async function getFallbackPayload(search: string | undefined, quality: string | undefined, page: number) {
  if (search?.trim() && (!quality || quality === '全部')) {
    const result = await getSearchPageEntries(search, page)

    return {
      entries: result.entries,
      total: result.total,
      hasMore: result.hasMore,
    }
  }

  const allEntries = await getAllSortedEntries()
  const filtered = filterEntries(allEntries, search, quality)
  const start = (page - 1) * PAGE_SIZE
  const entries = filtered.slice(start, start + PAGE_SIZE)

  return {
    entries,
    total: filtered.length,
    hasMore: start + entries.length < filtered.length,
  }
}

function isMissingSummaryTableError(error: unknown) {
  return (
    typeof error === 'object' &&
    error !== null &&
    'code' in error &&
    error.code === 'P2021'
  )
}

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url)
    const pageParam = searchParams.get('page')
    const page = pageParam ? Math.max(1, parseInt(pageParam, 10) || 1) : 1
    const search = searchParams.get('search') || undefined
    const quality = searchParams.get('quality') || undefined
    const where = buildCompanyValuationSummaryWhere(search, quality)
    const orderBy = buildCompanyValuationSummaryOrderBy(search, quality)
    const start = (page - 1) * PAGE_SIZE

    try {
      const [total, summaries] = await Promise.all([
        prisma.companyValuationSummary.count({ where }),
        prisma.companyValuationSummary.findMany({
          where,
          orderBy,
          skip: start,
          take: PAGE_SIZE,
          select: companyValuationListSummarySelect,
        }),
      ])

      const entries = summaries.map(companyValuationListCardFromSummary)

      return NextResponse.json({
        entries,
        total,
        page,
        pageSize: PAGE_SIZE,
        hasMore: start + entries.length < total,
      })
    } catch (error) {
      if (!isMissingSummaryTableError(error)) throw error

      const fallback = await getFallbackPayload(search, quality, page)
      return NextResponse.json({
        ...fallback,
        page,
        pageSize: PAGE_SIZE,
      })
    }
  } catch (error) {
    console.error('[company-valuation] load failed:', error)
    return NextResponse.json(
      { message: '公司估值数据获取失败' },
      { status: 500 },
    )
  }
}
