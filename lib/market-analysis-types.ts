export type MarketType = 'us' | 'hk' | 'a' | 'cn'
export type EntryType = 'manual' | 'ai-generated' | 'analysis' | 'research'
export type VisibilityType = 'draft' | 'published' | 'archived'
export type ExplanationType = 'price' | 'profit' | 'valuation' | 'business'
export type ImpactDirection = 'positive' | 'neutral' | 'negative'

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
  sourceUrls?: string[]
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
  rawJson?: string
}

export interface ValuationExplanationInput {
  valuationSnapshotId?: string
  explanationType: ExplanationType | string
  title: string
  body: string
  impactDirection?: ImpactDirection
  impactAmount?: number
  isRecurring?: boolean
  sourceUrls?: string[]
  confidence?: number
}

export interface MarketAnalysisWriteInput {
  company: CompanyInput
  pageEntry?: PageEntryInput
  exploration?: ExplorationInput
  valuation?: ValuationSnapshotInput
  explanations?: ValuationExplanationInput[]
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
  }
}
