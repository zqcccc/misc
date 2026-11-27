import { Prisma, PrismaClient } from '@prisma/client'
import type {
  Company,
  CompanyExploration,
  CompanyValuationExplanation,
  CompanyValuationSnapshot,
} from '@prisma/client'
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
  SourceUrlsInput,
  RawJsonInput,
  DexterInspiredAnalysisInput,
} from './market-analysis-types'
import { invalidateCompanyValuationCache } from '../app/api/company-valuation/cache'
import { refreshCompanyValuationSummary } from '../app/api/company-valuation/summary-store'
import { recordMarketAnalysisScratchpad } from './market-analysis-scratchpad'

export type { MarketType, EntryType, CompanyInput, PageEntryInput, ExplorationInput, ValuationSnapshotInput, ValuationExplanationInput, MarketAnalysisWriteInput, IdempotentWriteInput, CrossMarketWriteInput }

const prisma = new PrismaClient()

function normalizeSourceUrls(value: SourceUrlsInput | undefined) {
  if (value === undefined || value === null) return null

  const sourceUrls = Array.isArray(value) ? value : parseSourceUrlsString(value)
  const normalized = Array.from(
    new Set(
      sourceUrls
        .map((url) => url.trim())
        .filter((url) => url.length > 0),
    ),
  )

  return normalized.length > 0 ? JSON.stringify(normalized) : null
}

function parseSourceUrlsString(value: string) {
  const trimmed = value.trim()
  if (!trimmed) return []

  try {
    const parsed = JSON.parse(trimmed)
    if (Array.isArray(parsed)) {
      return parsed.filter((item): item is string => typeof item === 'string')
    }
  } catch {}

  return [trimmed]
}

function normalizeRawJson(value: RawJsonInput | undefined) {
  if (value === undefined || value === null) return null
  if (typeof value === 'string') return value.trim() || null

  return JSON.stringify(value)
}

function parseRawJson(value: RawJsonInput | undefined) {
  if (value === undefined || value === null) return null
  if (typeof value !== 'string') return value

  try {
    return JSON.parse(value) as unknown
  } catch {
    return value
  }
}

function mergeSourceUrls(
  value: SourceUrlsInput | undefined,
  extraSourceUrls: string[],
) {
  const sourceUrls = [
    ...(value === undefined || value === null
      ? []
      : Array.isArray(value)
        ? value
        : parseSourceUrlsString(value)),
    ...extraSourceUrls,
  ]
  const normalized = Array.from(
    new Set(sourceUrls.map((url) => url.trim()).filter((url) => url.length > 0)),
  )

  return normalized.length > 0 ? normalized : value
}

function collectAnalysisContextSourceUrls(
  analysisContext: DexterInspiredAnalysisInput | undefined,
) {
  if (!analysisContext) return []

  const sourceUrls: string[] = []
  for (const source of analysisContext.dataSources || []) {
    sourceUrls.push(...sourceUrlsFromInput(source.sourceUrls))
  }
  for (const result of analysisContext.toolResults || []) {
    sourceUrls.push(...sourceUrlsFromInput(result.sourceUrls))
  }

  return Array.from(new Set(sourceUrls))
}

function sourceUrlsFromInput(value: SourceUrlsInput | undefined) {
  if (value === undefined || value === null) return []
  return Array.isArray(value) ? value : parseSourceUrlsString(value)
}

function withAnalysisContext(
  exploration: ExplorationInput | undefined,
  analysisContext: DexterInspiredAnalysisInput | undefined,
) {
  if (!exploration || !analysisContext) return exploration

  const existingRawJson = parseRawJson(exploration.rawJson)
  const rawJson =
    existingRawJson && typeof existingRawJson === 'object' && !Array.isArray(existingRawJson)
      ? { ...existingRawJson, analysisContext }
      : { analysisContext, originalRawJson: existingRawJson }

  return {
    ...exploration,
    sourceUrls: mergeSourceUrls(
      exploration.sourceUrls,
      collectAnalysisContextSourceUrls(analysisContext),
    ),
    rawJson,
  }
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : String(error)
}

// 摘要刷新与缓存失效是写入成功的必要条件：
// - 摘要刷新在写入事务内执行，失败即整体回滚；
// - 缓存失效在事务提交后执行，失败将使 run 记为 failed 并向上抛出。
// SKIP_COMPANY_VALUATION_CACHE_INVALIDATION=1 为无 Redis 环境的显式豁免。
async function invalidateValuationCacheOrThrow() {
  if (process.env.SKIP_COMPANY_VALUATION_CACHE_INVALIDATION === '1') {
    return
  }

  await invalidateCompanyValuationCache()
}

async function ensureExplorationRun(runId: string) {
  const existingRun = await prisma.companyExplorationRun.findUnique({
    where: { id: runId },
  })
  if (existingRun) return

  await prisma.companyExplorationRun.create({
    data: {
      id: runId,
      prompt: `Market analysis run: ${runId}`,
      status: 'running',
    },
  })
}

async function markRunFinished(
  runId: string,
  status: 'completed' | 'failed',
  message?: string,
) {
  try {
    await prisma.companyExplorationRun.update({
      where: { id: runId },
      data: {
        status,
        finishedAt: new Date(),
        ...(status === 'failed' && message ? { error: message } : {}),
      },
    })
  } catch (error) {
    console.error(`[market-analysis] 更新 run 状态为 ${status} 失败 (${runId}):`, errorMessage(error))
  }
}

export async function disconnectMarketAnalysisClient() {
  await prisma.$disconnect()
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

// 公司幂等键：market + symbol（数据库已有唯一约束）
async function upsertCompanyInTx(tx: Prisma.TransactionClient, input: CompanyInput) {
  const detectedGroupId = input.groupId || detectGroupId(input.name)

  return tx.company.upsert({
    where: {
      market_symbol: {
        market: input.market,
        symbol: input.symbol,
      },
    },
    update: {
      name: input.name,
      exchange: input.exchange,
      currency: input.currency,
      sector: input.sector,
      industry: input.industry,
      country: input.country,
      website: input.website,
      groupId: detectedGroupId || undefined,
    },
    create: {
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

// 跨市场同步只补齐分组与市场级基础信息，不带入主市场的交易所/货币等差异字段
async function upsertCrossMarketCompanyInTx(
  tx: Prisma.TransactionClient,
  input: CompanyInput,
  groupId: string,
  targetMarket: string,
  targetSymbol: string,
) {
  return tx.company.upsert({
    where: {
      market_symbol: {
        market: targetMarket,
        symbol: targetSymbol,
      },
    },
    update: { groupId },
    create: {
      symbol: targetSymbol,
      market: targetMarket,
      name: input.name,
      groupId,
      sector: input.sector,
      industry: input.industry,
      country: input.country,
    },
  })
}

async function upsertPageEntryInTx(
  tx: Prisma.TransactionClient,
  companyId: string,
  input: PageEntryInput,
) {
  // 未提供的字段为 undefined，保持数据库现值
  return tx.company.update({
    where: { id: companyId },
    data: {
      entryType: input.entryType,
      entryNote: input.note,
      sortOrder: input.sortOrder,
      visible: input.visible,
    },
  })
}

async function upsertExplorationInTx(
  tx: Prisma.TransactionClient,
  companyId: string,
  input: ExplorationInput,
  runId?: string,
) {
  const data = {
    title: input.title,
    summary: input.summary,
    thesis: input.thesis,
    catalysts: input.catalysts,
    risks: input.risks,
    tags: input.tags ? JSON.stringify(input.tags) : null,
    score: input.score,
    confidence: input.confidence,
    sourceUrls: normalizeSourceUrls(input.sourceUrls),
    rawJson: normalizeRawJson(input.rawJson),
  }

  // 幂等键：companyId + runId；无 runId 的写入每次创建新版本
  if (runId) {
    return tx.companyExploration.upsert({
      where: { companyId_runId: { companyId, runId } },
      update: {
        ...data,
        visibility: input.visibility,
        pinned: input.pinned,
      },
      create: {
        companyId,
        runId,
        ...data,
        visibility: input.visibility ?? 'draft',
        pinned: input.pinned ?? false,
      },
    })
  }

  return tx.companyExploration.create({
    data: {
      companyId,
      runId: null,
      ...data,
      visibility: input.visibility ?? 'draft',
      pinned: input.pinned ?? false,
    },
  })
}

async function upsertValuationSnapshotInTx(
  tx: Prisma.TransactionClient,
  companyId: string,
  input: ValuationSnapshotInput,
  runId?: string,
) {
  const asOfDate = input.asOfDate instanceof Date
    ? input.asOfDate
    : new Date(input.asOfDate)

  const data = {
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
    rawJson: normalizeRawJson(input.rawJson),
  }

  // 幂等键：companyId + runId
  if (runId) {
    return tx.companyValuationSnapshot.upsert({
      where: { companyId_runId: { companyId, runId } },
      update: data,
      create: {
        companyId,
        runId,
        ...data,
      },
    })
  }

  return tx.companyValuationSnapshot.create({
    data: {
      companyId,
      runId: null,
      ...data,
    },
  })
}

async function upsertValuationExplanationInTx(
  tx: Prisma.TransactionClient,
  companyId: string,
  input: ValuationExplanationInput,
  runId?: string,
) {
  const data = {
    title: input.title,
    body: input.body,
    impactDirection: input.impactDirection,
    impactAmount: input.impactAmount,
    isRecurring: input.isRecurring,
    sourceUrls: normalizeSourceUrls(input.sourceUrls),
    confidence: input.confidence,
  }

  // 幂等键：companyId + runId + explanationType
  if (runId) {
    return tx.companyValuationExplanation.upsert({
      where: {
        companyId_runId_explanationType: {
          companyId,
          runId,
          explanationType: input.explanationType,
        },
      },
      update: {
        ...data,
        valuationSnapshotId: input.valuationSnapshotId,
      },
      create: {
        companyId,
        runId,
        valuationSnapshotId: input.valuationSnapshotId,
        explanationType: input.explanationType,
        ...data,
        authorType: 'ai',
      },
    })
  }

  return tx.companyValuationExplanation.create({
    data: {
      companyId,
      runId: null,
      valuationSnapshotId: input.valuationSnapshotId,
      explanationType: input.explanationType,
      ...data,
      authorType: 'ai',
    },
  })
}

type CompanyWriteResults = {
  company: Company
  pageEntry: Company | null
  exploration: CompanyExploration | null
  valuation: CompanyValuationSnapshot | null
  explanations: CompanyValuationExplanation[]
}

type CrossMarketSyncTarget = {
  market: string
  symbol: string
  companyId: string
  explorationId: string
}

async function writeCompanyRecordsInTx(
  marketAnalysisInput: MarketAnalysisWriteInput,
  runId: string | undefined,
): Promise<CompanyWriteResults> {
  const explorationInput = withAnalysisContext(marketAnalysisInput.exploration, marketAnalysisInput.analysisContext)

  return prisma.$transaction(async (tx) => {
    const company = await upsertCompanyInTx(tx, marketAnalysisInput.company)

    const results: CompanyWriteResults = {
      company,
      pageEntry: null,
      exploration: null,
      valuation: null,
      explanations: [],
    }

    if (marketAnalysisInput.pageEntry) {
      results.pageEntry = await upsertPageEntryInTx(tx, company.id, marketAnalysisInput.pageEntry)
    }

    if (explorationInput) {
      results.exploration = await upsertExplorationInTx(tx, company.id, explorationInput, runId)
    }

    if (marketAnalysisInput.valuation) {
      results.valuation = await upsertValuationSnapshotInTx(tx, company.id, marketAnalysisInput.valuation, runId)

      for (const explanation of marketAnalysisInput.explanations || []) {
        const written = await upsertValuationExplanationInTx(tx, company.id, {
          ...explanation,
          valuationSnapshotId: results.valuation.id,
        }, runId)
        results.explanations.push(written)
      }
    }

    // 摘要刷新在写入事务内执行：失败即整体回滚，不出现“数据已写入但摘要过期”的中间态
    await refreshCompanyValuationSummary(tx, company.id)

    return results
  })
}

async function syncExplorationsToCrossMarkets(
  marketAnalysisInput: MarketAnalysisWriteInput,
  runId: string,
  syncToMarkets?: CrossMarketWriteInput['syncToMarkets'],
): Promise<CrossMarketSyncTarget[]> {
  const groupId = marketAnalysisInput.company.groupId || detectGroupId(marketAnalysisInput.company.name)
  const explorationInput = withAnalysisContext(
    marketAnalysisInput.exploration,
    marketAnalysisInput.analysisContext,
  )

  if (!groupId || !explorationInput) return []

  const crossMarketSymbols = getCrossMarketSymbols(groupId)
  if (!crossMarketSymbols) return []

  const marketsToSync = syncToMarkets || Object.keys(crossMarketSymbols).filter(
    (m) => m !== marketAnalysisInput.company.market,
  )

  const syncedCompanies: CrossMarketSyncTarget[] = []

  for (const targetMarket of marketsToSync) {
    const targetSymbol = crossMarketSymbols[targetMarket]
    if (!targetSymbol) continue

    const synced = await prisma.$transaction(async (tx) => {
      const targetCompany = await upsertCrossMarketCompanyInTx(
        tx,
        marketAnalysisInput.company,
        groupId,
        targetMarket,
        targetSymbol,
      )

      if (marketAnalysisInput.pageEntry) {
        await upsertPageEntryInTx(tx, targetCompany.id, {
          ...marketAnalysisInput.pageEntry,
          title: marketAnalysisInput.pageEntry.title || marketAnalysisInput.company.name,
        })
      }

      const syncedExploration = await upsertExplorationInTx(tx, targetCompany.id, explorationInput, runId)

      await refreshCompanyValuationSummary(tx, targetCompany.id)

      return {
        market: targetMarket,
        symbol: targetSymbol,
        companyId: targetCompany.id,
        explorationId: syncedExploration.id,
      }
    })

    syncedCompanies.push(synced)
  }

  return syncedCompanies
}

export async function writeMarketAnalysisIdempotent(input: IdempotentWriteInput) {
  const { runId, ...marketAnalysisInput } = input

  await recordMarketAnalysisScratchpad(runId, 'init', {
    company: marketAnalysisInput.company,
    hasPageEntry: Boolean(marketAnalysisInput.pageEntry),
    hasExploration: Boolean(marketAnalysisInput.exploration),
    hasValuation: Boolean(marketAnalysisInput.valuation),
    explanationsCount: marketAnalysisInput.explanations?.length || 0,
    hasAnalysisContext: Boolean(marketAnalysisInput.analysisContext),
    toolResultsCount: marketAnalysisInput.analysisContext?.toolResults?.length || 0,
  })

  for (const toolResult of marketAnalysisInput.analysisContext?.toolResults || []) {
    await recordMarketAnalysisScratchpad(
      runId,
      'tool_result',
      toolResult as unknown as Record<string, unknown>,
    )
  }

  try {
    await ensureExplorationRun(runId)

    const results = await writeCompanyRecordsInTx(marketAnalysisInput, runId)

    // 缓存失效是必要成功条件：失败 → run 记 failed 并向上抛出
    await invalidateValuationCacheOrThrow()
    await markRunFinished(runId, 'completed')

    await recordMarketAnalysisScratchpad(runId, 'write_result', {
      companyId: results.company.id,
      pageEntryId: results.pageEntry?.id || null,
      explorationId: results.exploration?.id || null,
      valuationId: results.valuation?.id || null,
      explanationsCount: results.explanations.length,
    })

    return results
  } catch (error) {
    await recordMarketAnalysisScratchpad(runId, 'error', {
      stage: 'write',
      message: errorMessage(error),
    })
    await markRunFinished(runId, 'failed', errorMessage(error))
    throw error
  }
}

export async function writeMarketAnalysisCrossMarket(input: CrossMarketWriteInput) {
  const { runId, syncToMarkets, ...marketAnalysisInput } = input

  await recordMarketAnalysisScratchpad(runId, 'init', {
    company: marketAnalysisInput.company,
    hasPageEntry: Boolean(marketAnalysisInput.pageEntry),
    hasExploration: Boolean(marketAnalysisInput.exploration),
    hasValuation: Boolean(marketAnalysisInput.valuation),
    explanationsCount: marketAnalysisInput.explanations?.length || 0,
    hasAnalysisContext: Boolean(marketAnalysisInput.analysisContext),
    toolResultsCount: marketAnalysisInput.analysisContext?.toolResults?.length || 0,
  })

  for (const toolResult of marketAnalysisInput.analysisContext?.toolResults || []) {
    await recordMarketAnalysisScratchpad(
      runId,
      'tool_result',
      toolResult as unknown as Record<string, unknown>,
    )
  }

  try {
    await ensureExplorationRun(runId)

    const primaryResult = await writeCompanyRecordsInTx(marketAnalysisInput, runId)
    const syncedCompanies = await syncExplorationsToCrossMarkets(marketAnalysisInput, runId, syncToMarkets)

    await invalidateValuationCacheOrThrow()
    await markRunFinished(runId, 'completed')

    await recordMarketAnalysisScratchpad(runId, 'write_result', {
      stage: 'cross_market_sync',
      companyId: primaryResult.company.id,
      explorationId: primaryResult.exploration?.id || null,
      valuationId: primaryResult.valuation?.id || null,
      explanationsCount: primaryResult.explanations.length,
      syncedCompanies,
    })

    return {
      ...primaryResult,
      syncedCompanies,
    }
  } catch (error) {
    await recordMarketAnalysisScratchpad(runId, 'error', {
      stage: 'cross_market_sync',
      message: errorMessage(error),
    })
    await markRunFinished(runId, 'failed', errorMessage(error))
    throw error
  }
}
