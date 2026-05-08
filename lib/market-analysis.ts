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
  IdempotentWriteInput,
  CrossMarketWriteInput,
} from './market-analysis-types'
import { invalidateCompanyValuationCache } from '../app/api/company-valuation/cache'

export type { MarketType, EntryType, CompanyInput, PageEntryInput, ExplorationInput, ValuationSnapshotInput, ValuationExplanationInput, MarketAnalysisWriteInput, IdempotentWriteInput, CrossMarketWriteInput }

const prisma = new PrismaClient()

async function invalidateValuationCacheAfterWrite() {
  try {
    await invalidateCompanyValuationCache()
  } catch (error) {
    console.warn('[market-analysis] invalidate company valuation cache failed:', error)
  }
}

// 跨市场 symbol 映射表（常见 A+H 股）
//  key: groupId, value: { market: symbol }
const CROSS_MARKET_SYMBOLS: Record<string, Record<string, string>> = {
  '新华保险': { a: '601336', hk: '01336' },
  '中国平安': { a: '601318', hk: '02318' },
  '招商银行': { a: '600036', hk: '03968' },
  '中信证券': { a: '600030', hk: '06030' },
  '海通证券': { a: '600837', hk: '06837' },
  '中国中铁': { a: '601390', hk: '00390' },
  '中国铁建': { a: '601186', hk: '01186' },
  '中国建筑': { a: '601668', hk: '03311' },
  '中国中车': { a: '601766', hk: '01766' },
  '中国石油': { a: '601857', hk: '00857' },
  '中国石化': { a: '600028', hk: '00386' },
  '中国神华': { a: '601088', hk: '01088' },
  '建设银行': { a: '601939', hk: '00939' },
  '工商银行': { a: '601398', hk: '01398' },
  '农业银行': { a: '601288', hk: '01288' },
  '中国银行': { a: '601988', hk: '03988' },
  '交通银行': { a: '601328', hk: '03328' },
  '中国人寿': { a: '601628', hk: '02628' },
  '太平洋保险': { a: '601601', hk: '02601' },
  '民生银行': { a: '600016', hk: '01988' },
}

export function getCrossMarketSymbols(groupId: string): Record<string, string> | null {
  return CROSS_MARKET_SYMBOLS[groupId] || null
}

export function detectGroupId(companyName: string): string | null {
  // 根据公司名称匹配 groupId
  for (const groupId of Object.keys(CROSS_MARKET_SYMBOLS)) {
    if (companyName.includes(groupId)) {
      return groupId
    }
  }
  return null
}

export async function findOrCreateCompany(input: CompanyInput) {
  const existingCompany = await prisma.company.findUnique({
    where: {
      market_symbol: {
        market: input.market,
        symbol: input.symbol,
      },
    },
  })

  // 自动检测 groupId
  const detectedGroupId = input.groupId || detectGroupId(input.name)

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
        groupId: detectedGroupId || existingCompany.groupId,
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
      groupId: detectedGroupId,
    },
  })
}

export async function findRelatedCompanies(companyId: string) {
  const company = await prisma.company.findUnique({
    where: { id: companyId },
  })

  if (!company || !company.groupId) {
    return []
  }

  return prisma.company.findMany({
    where: {
      groupId: company.groupId,
      id: { not: companyId },
    },
  })
}

export async function upsertPageEntry(
  companyId: string,
  input: PageEntryInput,
) {
  const existingCompany = await prisma.company.findUnique({
    where: { id: companyId },
  })

  if (!existingCompany) {
    throw new Error(`Company not found: ${companyId}`)
  }

  return prisma.company.update({
    where: { id: companyId },
    data: {
      entryType: input.entryType,
      entryNote: input.note,
      sortOrder: input.sortOrder ?? existingCompany.sortOrder,
      visible: input.visible ?? existingCompany.visible,
    },
  })
}

export async function upsertExploration(
  companyId: string,
  input: ExplorationInput,
  runId?: string,
) {
  if (runId) {
    const existing = await prisma.companyExploration.findFirst({
      where: {
        companyId,
        runId,
      },
    })

    if (existing) {
      return prisma.companyExploration.update({
        where: { id: existing.id },
        data: {
          title: input.title,
          summary: input.summary,
          thesis: input.thesis,
          catalysts: input.catalysts,
          risks: input.risks,
          tags: input.tags ? JSON.stringify(input.tags) : null,
          score: input.score,
          confidence: input.confidence,
          sourceUrls: input.sourceUrls ? JSON.stringify(input.sourceUrls) : null,
          visibility: input.visibility ?? existing.visibility,
          pinned: input.pinned ?? existing.pinned,
        },
      })
    }
  }

  return prisma.companyExploration.create({
    data: {
      companyId,
      runId: runId || null,
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
    },
  })
}

export async function upsertValuationSnapshot(
  companyId: string,
  input: ValuationSnapshotInput,
  runId?: string,
) {
  const asOfDate = input.asOfDate instanceof Date
    ? input.asOfDate
    : new Date(input.asOfDate)

  if (runId) {
    const existing = await prisma.companyValuationSnapshot.findFirst({
      where: {
        companyId,
        runId,
      },
    })

    if (existing) {
      return prisma.companyValuationSnapshot.update({
        where: { id: existing.id },
        data: {
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
  }

  return prisma.companyValuationSnapshot.create({
    data: {
      companyId,
      runId: runId || null,
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

export async function upsertValuationExplanation(
  companyId: string,
  input: ValuationExplanationInput,
  runId?: string,
) {
  if (runId) {
    const existing = await prisma.companyValuationExplanation.findFirst({
      where: {
        companyId,
        runId,
        explanationType: input.explanationType,
      },
    })

    if (existing) {
      return prisma.companyValuationExplanation.update({
        where: { id: existing.id },
        data: {
          valuationSnapshotId: input.valuationSnapshotId,
          title: input.title,
          body: input.body,
          impactDirection: input.impactDirection,
          impactAmount: input.impactAmount,
          isRecurring: input.isRecurring,
          sourceUrls: input.sourceUrls ? JSON.stringify(input.sourceUrls) : null,
          confidence: input.confidence,
        },
      })
    }
  }

  return prisma.companyValuationExplanation.create({
    data: {
      companyId,
      runId: runId || null,
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
    results.pageEntry = await upsertPageEntry(company.id, input.pageEntry)
  }

  if (input.exploration) {
    results.exploration = await upsertExploration(company.id, input.exploration)
  }

  if (input.valuation) {
    results.valuation = await upsertValuationSnapshot(company.id, input.valuation)

    if (input.explanations && input.explanations.length > 0) {
      for (const explanation of input.explanations) {
        const exp = await upsertValuationExplanation(company.id, {
          ...explanation,
          valuationSnapshotId: results.valuation.id,
        })
        results.explanations.push(exp)
      }
    }
  }

  await invalidateValuationCacheAfterWrite()

  return results
}

export async function writeMarketAnalysisIdempotent(input: IdempotentWriteInput) {
  const { runId, ...marketAnalysisInput } = input

  const company = await findOrCreateCompany(marketAnalysisInput.company)

  const results: any = {
    company,
    pageEntry: null,
    exploration: null,
    valuation: null,
    explanations: [],
  }

  if (marketAnalysisInput.pageEntry) {
    results.pageEntry = await upsertPageEntry(company.id, marketAnalysisInput.pageEntry)
  }

  if (marketAnalysisInput.exploration) {
    results.exploration = await upsertExploration(
      company.id,
      marketAnalysisInput.exploration,
      runId,
    )
  }

  if (marketAnalysisInput.valuation) {
    results.valuation = await upsertValuationSnapshot(
      company.id,
      marketAnalysisInput.valuation,
      runId,
    )

    if (marketAnalysisInput.explanations && marketAnalysisInput.explanations.length > 0) {
      for (const explanation of marketAnalysisInput.explanations) {
        const exp = await upsertValuationExplanation(company.id, {
          ...explanation,
          valuationSnapshotId: results.valuation.id,
        }, runId)
        results.explanations.push(exp)
      }
    }
  }

  await invalidateValuationCacheAfterWrite()

  return results
}

export async function writeMarketAnalysisCrossMarket(input: CrossMarketWriteInput) {
  const { runId, syncToMarkets, ...marketAnalysisInput } = input

  // 1. 写入主市场公司
  const primaryResult = await writeMarketAnalysisIdempotent({
    ...marketAnalysisInput,
    runId,
  })

  const syncedCompanies: {
    market: string
    symbol: string
    companyId: string
    explorationId: string
  }[] = []

  // 2. 如果提供了 groupId，同步 exploration 到其他市场
  const groupId = marketAnalysisInput.company.groupId || detectGroupId(marketAnalysisInput.company.name)

  if (groupId && marketAnalysisInput.exploration) {
    const crossMarketSymbols = getCrossMarketSymbols(groupId)

    if (crossMarketSymbols) {
      // 确定要同步的市场
      const marketsToSync = syncToMarkets || Object.keys(crossMarketSymbols).filter(
        m => m !== marketAnalysisInput.company.market
      )

      for (const targetMarket of marketsToSync) {
        const targetSymbol = crossMarketSymbols[targetMarket]
        if (!targetSymbol) continue

        // 查找或创建目标市场的公司记录
        let targetCompany = await prisma.company.findUnique({
          where: {
            market_symbol: {
              market: targetMarket,
              symbol: targetSymbol,
            },
          },
        })

        if (!targetCompany) {
          targetCompany = await prisma.company.create({
            data: {
              symbol: targetSymbol,
              market: targetMarket,
              name: marketAnalysisInput.company.name,
              groupId: groupId,
              sector: marketAnalysisInput.company.sector,
              industry: marketAnalysisInput.company.industry,
              country: marketAnalysisInput.company.country,
            },
          })
        } else if (!targetCompany.groupId) {
          // 更新 groupId
          targetCompany = await prisma.company.update({
            where: { id: targetCompany.id },
            data: { groupId },
          })
        }

        // 同步创建 PageEntry（如果主市场有）
        if (marketAnalysisInput.pageEntry) {
          await upsertPageEntry(targetCompany.id, {
            ...marketAnalysisInput.pageEntry,
            title: marketAnalysisInput.pageEntry.title || marketAnalysisInput.company.name,
          })
        }

        // 同步 exploration（使用相同的 runId）
        const syncedExploration = await upsertExploration(
          targetCompany.id,
          marketAnalysisInput.exploration,
          runId,
        )

        syncedCompanies.push({
          market: targetMarket,
          symbol: targetSymbol,
          companyId: targetCompany.id,
          explorationId: syncedExploration.id,
        })
      }
    }
  }

  await invalidateValuationCacheAfterWrite()

  return {
    ...primaryResult,
    syncedCompanies,
  }
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
    },
  })
}

export async function getCompanyGroupMembers(groupId: string) {
  return prisma.company.findMany({
    where: { groupId },
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
    },
  })
}
