import { Prisma } from '@prisma/client'
import type { PrismaClient } from '@prisma/client'
import { companyInclude } from './query'
import {
  buildCompanyValuationCard,
  parseJsonArray,
  type CompanyValuationCard,
  type CompanyValuationCardInput,
  type CompanyValuationExplanationInput,
} from './summary'

const COMPANY_VALUATION_SUMMARY_BATCH_SIZE = 100
const PROFIT_QUALITY_RANK: Record<CompanyValuationCard['profitQuality'], number> = {
  正常: 0,
  待确认: 1,
  需调整: 2,
}

type CompanyValuationSummaryInput = CompanyValuationCardInput & {
  company: CompanyValuationCardInput['company'] & {
    sortOrder?: number | null
    updatedAt?: Date | string | null
    visible?: boolean | null
  }
  searchTags?: readonly string[]
}

type CompanyWithValuationInclude = Prisma.CompanyGetPayload<{
  include: typeof companyInclude
}>

function buildSearchText(
  card: CompanyValuationCard,
  searchTags: readonly string[] = [],
) {
  return [card.title, card.symbol, ...card.tags, ...searchTags]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
}

function companyUpdatedAt(input: CompanyValuationSummaryInput) {
  if (!input.company.updatedAt) return new Date()
  return input.company.updatedAt instanceof Date
    ? input.company.updatedAt
    : new Date(input.company.updatedAt)
}

function nullableJson(value: unknown) {
  return value === null ? Prisma.DbNull : value as Prisma.InputJsonValue
}

function buildCompanyValuationSummaryData(input: CompanyValuationSummaryInput) {
  const card = buildCompanyValuationCard(input)

  return {
    symbol: card.symbol,
    market: card.market,
    title: card.title,
    currency: card.currency,
    entryType: card.entryType,
    entryNote: card.entryNote,
    metrics: card.metrics as unknown as Prisma.InputJsonValue,
    exploration: card.exploration as unknown as Prisma.InputJsonValue,
    tags: card.tags as unknown as Prisma.InputJsonValue,
    profitQuality: card.profitQuality,
    profitQualityRank: PROFIT_QUALITY_RANK[card.profitQuality],
    primaryExplanation: nullableJson(card.primaryExplanation),
    explanations: card.explanations as unknown as Prisma.InputJsonValue,
    explorationScore: card.exploration.score ?? 0,
    sortOrder: input.company.sortOrder ?? 0,
    companyUpdatedAt: companyUpdatedAt(input),
    searchText: buildSearchText(card, input.searchTags),
    visible: input.company.visible ?? true,
  }
}

function buildCompanyValuationSummaryDataFromCompany(
  company: CompanyWithValuationInclude,
  searchTags: readonly string[] = [],
) {
  return buildCompanyValuationSummaryData({
    company,
    latestValuation: company.valuations[0] || null,
    latestExploration: company.explorations[0] || null,
    explanations: company.explanations,
    searchTags,
  })
}

function tagsFromExplorations(explorations: readonly { tags: string | null }[]) {
  return Array.from(
    new Set(explorations.flatMap((exploration) => parseJsonArray(exploration.tags))),
  )
}

function jsonObject<T>(value: Prisma.JsonValue, fallback: T) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return fallback
  return value as T
}

function jsonArray<T>(value: Prisma.JsonValue) {
  if (!Array.isArray(value)) return []
  return value as T[]
}

export const companyValuationListSummarySelect = {
  companyId: true,
  symbol: true,
  market: true,
  title: true,
  currency: true,
  entryType: true,
  entryNote: true,
  metrics: true,
  exploration: true,
  tags: true,
  profitQuality: true,
} satisfies Prisma.CompanyValuationSummarySelect

export function companyValuationListCardFromSummary(
  summary: Prisma.CompanyValuationSummaryGetPayload<{
    select: typeof companyValuationListSummarySelect
  }>,
): CompanyValuationCard {
  return {
    id: summary.companyId,
    symbol: summary.symbol,
    market: summary.market,
    title: summary.title,
    currency: summary.currency,
    entryType: summary.entryType,
    entryNote: summary.entryNote,
    metrics: jsonObject<CompanyValuationCard['metrics']>(summary.metrics, {
      asOfDate: null,
      price: null,
      ttmEps: null,
      ttmPe: null,
      profitLinePrice: null,
      referenceLinePrice: null,
      upsideToProfitLine: null,
      upsideToReferenceLine: null,
    }),
    exploration: jsonObject<CompanyValuationCard['exploration']>(summary.exploration, {
      summary: null,
      thesis: null,
      score: null,
    }),
    tags: jsonArray<string>(summary.tags),
    profitQuality: summary.profitQuality as CompanyValuationCard['profitQuality'],
    primaryExplanation: null,
    explanations: [],
  }
}

export function companyValuationCardFromSummary(
  summary: Prisma.CompanyValuationSummaryGetPayload<object>,
): CompanyValuationCard {
  return {
    id: summary.companyId,
    symbol: summary.symbol,
    market: summary.market,
    title: summary.title,
    currency: summary.currency,
    entryType: summary.entryType,
    entryNote: summary.entryNote,
    metrics: jsonObject<CompanyValuationCard['metrics']>(summary.metrics, {
      asOfDate: null,
      price: null,
      ttmEps: null,
      ttmPe: null,
      profitLinePrice: null,
      referenceLinePrice: null,
      upsideToProfitLine: null,
      upsideToReferenceLine: null,
    }),
    exploration: jsonObject<CompanyValuationCard['exploration']>(summary.exploration, {
      summary: null,
      thesis: null,
      score: null,
    }),
    tags: jsonArray<string>(summary.tags),
    profitQuality: summary.profitQuality as CompanyValuationCard['profitQuality'],
    primaryExplanation: summary.primaryExplanation
      ? jsonObject<CompanyValuationExplanationInput>(summary.primaryExplanation, {
          explanationType: 'profit',
          title: '',
          body: '',
        })
      : null,
    explanations: jsonArray<CompanyValuationExplanationInput>(summary.explanations),
  }
}

export async function refreshCompanyValuationSummary(
  prisma: PrismaClient,
  companyId: string,
) {
  const company = await prisma.company.findUnique({
    where: { id: companyId },
    include: companyInclude,
  })

  if (!company) return null

  const explorations = await prisma.companyExploration.findMany({
    where: { companyId, visibility: 'published' },
    select: { tags: true },
  })
  const data = buildCompanyValuationSummaryDataFromCompany(
    company,
    tagsFromExplorations(explorations),
  )

  return prisma.companyValuationSummary.upsert({
    where: { companyId },
    create: {
      companyId,
      ...data,
    },
    update: data,
  })
}

export async function rebuildCompanyValuationSummaries(prisma: PrismaClient) {
  let cursor: { id: string } | undefined
  let count = 0

  while (true) {
    const companies = await prisma.company.findMany({
      include: companyInclude,
      orderBy: { id: 'asc' },
      take: COMPANY_VALUATION_SUMMARY_BATCH_SIZE,
      ...(cursor ? { cursor, skip: 1 } : {}),
    })

    if (companies.length === 0) break

    const companyIds = companies.map((company) => company.id)
    const explorationTags = await prisma.companyExploration.findMany({
      where: {
        companyId: { in: companyIds },
        visibility: 'published',
      },
      select: {
        companyId: true,
        tags: true,
      },
    })
    const tagsByCompanyId = new Map<string, string[]>()
    for (const exploration of explorationTags) {
      const tags = tagsByCompanyId.get(exploration.companyId) || []
      tags.push(...parseJsonArray(exploration.tags))
      tagsByCompanyId.set(exploration.companyId, Array.from(new Set(tags)))
    }

    for (const company of companies) {
      const data = buildCompanyValuationSummaryDataFromCompany(
        company,
        tagsByCompanyId.get(company.id),
      )
      await prisma.companyValuationSummary.upsert({
        where: { companyId: company.id },
        create: {
          companyId: company.id,
          ...data,
        },
        update: data,
      })
      count += 1
    }

    cursor = { id: companies[companies.length - 1].id }
  }

  return count
}
