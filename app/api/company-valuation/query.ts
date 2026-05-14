import type { Prisma } from '@prisma/client'

export const companyInclude = {
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

export function buildCompanyValuationWhere(
  search?: string,
): Prisma.CompanyWhereInput {
  const query = search?.trim()
  if (!query) return { visible: true }

  return {
    visible: true,
    OR: [
      { name: { contains: query, mode: 'insensitive' } },
      { symbol: { contains: query, mode: 'insensitive' } },
      {
        explorations: {
          some: {
            visibility: 'published',
            tags: { contains: query, mode: 'insensitive' },
          },
        },
      },
    ],
  }
}

export const companyValuationOrderBy = [
  { sortOrder: 'desc' as const },
  { updatedAt: 'desc' as const },
  { name: 'asc' as const },
]

export function buildCompanyValuationSummaryWhere(
  search?: string,
  quality?: string,
): Prisma.CompanyValuationSummaryWhereInput {
  const where: Prisma.CompanyValuationSummaryWhereInput = { visible: true }
  const query = search?.trim()

  if (quality && quality !== '全部') {
    where.profitQuality = quality
  }

  if (query) {
    where.searchText = { contains: query.toLowerCase(), mode: 'insensitive' }
  }

  return where
}

const defaultCompanyValuationSummaryOrderBy = [
  { profitQualityRank: 'asc' as const },
  { explorationScore: 'desc' as const },
  { updatedAt: 'desc' as const },
  { title: 'asc' as const },
]

const searchCompanyValuationSummaryOrderBy = [
  { sortOrder: 'desc' as const },
  { companyUpdatedAt: 'desc' as const },
  { title: 'asc' as const },
]

export function buildCompanyValuationSummaryOrderBy(
  search?: string,
  quality?: string,
) {
  if (search?.trim() && (!quality || quality === '全部')) {
    return searchCompanyValuationSummaryOrderBy
  }

  return defaultCompanyValuationSummaryOrderBy
}
