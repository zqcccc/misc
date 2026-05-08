import { PrismaClient } from '@prisma/client'
import type {
  MarketType,
  EntryType,
  CompanyInput,
  PageEntryInput,
  ExplorationInput,
  ValuationSnapshotInput,
  ValuationExplanationInput,
  MarketAnalysisWriteInput,
} from './market-analysis-types'

export type { MarketType, EntryType, CompanyInput, PageEntryInput, ExplorationInput, ValuationSnapshotInput, ValuationExplanationInput, MarketAnalysisWriteInput }

const prisma = new PrismaClient()

export async function findOrCreateCompany(input: CompanyInput) {
  const existingCompany = await prisma.company.findUnique({
    where: {
      market_symbol: {
        market: input.market,
        symbol: input.symbol,
      },
    },
  })

  if (existingCompany) {
    return prisma.company.update({
      where: { id: existingCompany.id },
      data: {
        name: input.name,
        exchange: input.exchange,
        currency: input.currency,
        sector: input.sector,
        industry: input.industry,
        country: input.country,
        website: input.website,
      },
    })
  }

  return prisma.company.create({
    data: {
      symbol: input.symbol,
      market: input.market,
      exchange: input.exchange,
      name: input.name,
      currency: input.currency,
      sector: input.sector,
      industry: input.industry,
      country: input.country,
      website: input.website,
    },
  })
}

export async function createPageEntry(
  companyId: string,
  input: PageEntryInput,
) {
  const existingEntry = await prisma.companyPageEntry.findFirst({
    where: {
      companyId,
      entryType: input.entryType,
    },
  })

  if (existingEntry) {
    return prisma.companyPageEntry.update({
      where: { id: existingEntry.id },
      data: {
        title: input.title,
        note: input.note,
        sortOrder: input.sortOrder ?? existingEntry.sortOrder,
        visible: input.visible ?? existingEntry.visible,
      },
    })
  }

  return prisma.companyPageEntry.create({
    data: {
      companyId,
      entryType: input.entryType,
      title: input.title,
      note: input.note,
      sortOrder: input.sortOrder ?? 0,
      visible: input.visible ?? true,
    },
  })
}

export async function createExploration(
  companyId: string,
  input: ExplorationInput,
) {
  const data: any = {
    companyId,
    title: input.title,
    summary: input.summary,
    thesis: input.thesis,
    catalysts: input.catalysts,
    risks: input.risks,
    tags: input.tags ? JSON.stringify(input.tags) : null,
    score: input.score,
    confidence: input.confidence,
    sourceUrls: input.sourceUrls ? JSON.stringify(input.sourceUrls) : null,
    visibility: input.visibility ?? 'draft',
    pinned: input.pinned ?? false,
  }

  return prisma.companyExploration.create({
    data,
  })
}

export async function createValuationSnapshot(
  companyId: string,
  input: ValuationSnapshotInput,
) {
  const asOfDate = input.asOfDate instanceof Date
    ? input.asOfDate
    : new Date(input.asOfDate)

  return prisma.companyValuationSnapshot.create({
    data: {
      companyId,
      asOfDate,
      price: input.price,
      marketCap: input.marketCap,
      ttmEps: input.ttmEps,
      normalizedTtmEps: input.normalizedTtmEps,
      ttmPe: input.ttmPe,
      normalizedTtmPe: input.normalizedTtmPe,
      revenueTtm: input.revenueTtm,
      profitTtm: input.profitTtm,
      normalizedProfitTtm: input.normalizedProfitTtm,
      profitMultiple: input.profitMultiple,
      referenceMultiple: input.referenceMultiple,
      profitLinePrice: input.profitLinePrice,
      referenceLinePrice: input.referenceLinePrice,
      upsideToProfitLine: input.upsideToProfitLine,
      upsideToReferenceLine: input.upsideToReferenceLine,
      nonRecurringProfit: input.nonRecurringProfit,
      profitQualityScore: input.profitQualityScore,
      profitQualitySummary: input.profitQualitySummary,
      source: input.source,
      rawJson: input.rawJson,
    },
  })
}

export async function createValuationExplanation(
  companyId: string,
  input: ValuationExplanationInput,
) {
  return prisma.companyValuationExplanation.create({
    data: {
      companyId,
      valuationSnapshotId: input.valuationSnapshotId,
      explanationType: input.explanationType,
      title: input.title,
      body: input.body,
      impactDirection: input.impactDirection,
      impactAmount: input.impactAmount,
      isRecurring: input.isRecurring,
      sourceUrls: input.sourceUrls ? JSON.stringify(input.sourceUrls) : null,
      confidence: input.confidence,
      authorType: 'ai',
    },
  })
}

export async function writeMarketAnalysis(input: MarketAnalysisWriteInput) {
  const company = await findOrCreateCompany(input.company)

  const results: any = {
    company,
    pageEntry: null,
    exploration: null,
    valuation: null,
    explanations: [],
  }

  if (input.pageEntry) {
    results.pageEntry = await createPageEntry(company.id, input.pageEntry)
  }

  if (input.exploration) {
    results.exploration = await createExploration(company.id, input.exploration)
  }

  if (input.valuation) {
    results.valuation = await createValuationSnapshot(company.id, input.valuation)

    if (input.explanations && input.explanations.length > 0) {
      for (const explanation of input.explanations) {
        const exp = await createValuationExplanation(company.id, {
          ...explanation,
          valuationSnapshotId: results.valuation.id,
        })
        results.explanations.push(exp)
      }
    }
  }

  return results
}

export async function getCompanyByMarketSymbol(
  market: string,
  symbol: string,
) {
  return prisma.company.findUnique({
    where: {
      market_symbol: {
        market,
        symbol,
      },
    },
    include: {
      valuations: {
        orderBy: [{ asOfDate: 'desc' }, { createdAt: 'desc' }],
        take: 1,
      },
      explorations: {
        where: { visibility: 'published' },
        orderBy: [{ pinned: 'desc' }, { createdAt: 'desc' }],
        take: 1,
      },
      explanations: {
        where: { isCurrent: true },
        orderBy: [{ asOfDate: 'desc' }, { createdAt: 'desc' }],
        take: 8,
      },
      pageEntries: true,
    },
  })
}
