export type MarketType = 'us' | 'hk' | 'a' | 'cn'
export type EntryType = 'manual' | 'ai-generated' | 'analysis' | 'research'
export type VisibilityType = 'draft' | 'published' | 'archived'
export type ExplanationType = 'price' | 'profit' | 'valuation' | 'business'
export type ImpactDirection = 'positive' | 'neutral' | 'negative'
export type SourceUrlsInput = string | string[] | null
export type RawJsonInput = string | Record<string, unknown> | unknown[] | null
export type AnalysisChecklistStatus = 'done' | 'missing' | 'not_applicable'

export interface AnalysisDataSourceInput {
  provider: string
  description?: string
  sourceUrls?: SourceUrlsInput
  fetchedAt?: string
  rawJson?: RawJsonInput
}

export interface AnalysisToolResultInput {
  tool: string
  query?: string
  args?: Record<string, unknown>
  data?: unknown
  summary?: string
  sourceUrls?: SourceUrlsInput
  error?: string | null
}

export interface AnalysisChecklistInput {
  item: string
  status: AnalysisChecklistStatus | string
  note?: string
}

export interface DexterInspiredAnalysisInput {
  financialStatements?: {
    incomeStatement?: boolean
    balanceSheet?: boolean
    cashFlowStatement?: boolean
    keyRatios?: boolean
    historicalKeyRatios?: boolean
    earnings?: boolean
    segments?: boolean
  }
  dataSources?: AnalysisDataSourceInput[]
  toolResults?: AnalysisToolResultInput[]
  checklist?: AnalysisChecklistInput[]
}

export interface CompanyInput {
  symbol: string
  market: MarketType | string
  exchange?: string
  name: string
  currency?: string
  sector?: string
  industry?: string
  country?: string
  website?: string
  groupId?: string  // 跨市场关联标识，如 "新华保险"
}

export interface PageEntryInput {
  entryType: EntryType | string
  title?: string
  note?: string
  sortOrder?: number
  visible?: boolean
}

export interface ExplorationInput {
  title: string
  summary: string
  thesis?: string
  catalysts?: string
  risks?: string
  tags?: string[]
  score?: number
  confidence?: number
  sourceUrls?: SourceUrlsInput
  rawJson?: RawJsonInput
  visibility?: VisibilityType
  pinned?: boolean
}

export interface ValuationSnapshotInput {
  asOfDate: Date | string
  price?: number
  marketCap?: number
  ttmEps?: number
  normalizedTtmEps?: number
  ttmPe?: number
  normalizedTtmPe?: number
  revenueTtm?: number
  profitTtm?: number
  normalizedProfitTtm?: number
  profitMultiple?: number
  referenceMultiple?: number
  profitLinePrice?: number
  referenceLinePrice?: number
  upsideToProfitLine?: number
  upsideToReferenceLine?: number
  nonRecurringProfit?: number
  profitQualityScore?: number
  profitQualitySummary?: string
  source?: string
  rawJson?: RawJsonInput
}

export interface ValuationExplanationInput {
  valuationSnapshotId?: string
  explanationType: ExplanationType | string
  title: string
  body: string
  impactDirection?: ImpactDirection
  impactAmount?: number
  isRecurring?: boolean
  sourceUrls?: SourceUrlsInput
  confidence?: number
}

export interface MarketAnalysisWriteInput {
  company: CompanyInput
  pageEntry?: PageEntryInput
  exploration?: ExplorationInput
  valuation?: ValuationSnapshotInput
  explanations?: ValuationExplanationInput[]
  analysisContext?: DexterInspiredAnalysisInput
}

export interface IdempotentWriteInput extends MarketAnalysisWriteInput {
  runId: string
}

export interface CrossMarketWriteInput extends IdempotentWriteInput {
  // 当分析涉及多市场时，提供其他市场的 symbol 信息
  // 系统会自动同步 exploration 到关联的市场公司
  syncToMarkets?: ('us' | 'hk' | 'a' | 'cn')[]
}

export interface WriteResult {
  success: boolean
  message?: string
  error?: string
  data?: {
    company: {
      id: string
      symbol: string
      market: string
      name: string
    }
    pageEntry: {
      id: string
      entryType: string
    } | null
    exploration: {
      id: string
      title: string
    } | null
    valuation: {
      id: string
      asOfDate: Date | string
    } | null
    explanationsCount: number
    syncedCompanies?: {
      market: string
      symbol: string
      companyId: string
      explorationId: string
    }[]
  }
}
