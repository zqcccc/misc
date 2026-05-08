export type ProfitPoint = {
  date: string
  quarter: string
  eps: number
  ttmEps: number | null
  price: number | null
  ttmPe: number | null
}

export type ProfitLineData = {
  symbol: string
  name: string
  market?: 'us' | 'cn' | 'hk'
  currency: string
  points: ProfitPoint[]
  latestPrice?: {
    date: string
    price: number
  } | null
  sources: {
    eps: string
    price: string
  }
  ttmMethod?: 'quarterly-rollup' | 'source-eps-ttm'
  epsCurrency?: string
  fxRate?: number
}

export type ValuationExplanation = {
  explanationType: string
  title: string
  body: string
  impactDirection?: string | null
  isRecurring?: boolean | null
  confidence?: number | null
}

export type CompanyValuationCard = {
  id: string
  symbol: string
  market: string
  title: string
  currency: string | null
  entryType: string
  entryNote: string | null
  metrics: {
    asOfDate: string | null
    price: number | null
    ttmEps: number | null
    ttmPe: number | null
    profitLinePrice: number | null
    referenceLinePrice: number | null
    upsideToProfitLine: number | null
    upsideToReferenceLine: number | null
  }
  exploration: {
    summary: string | null
    thesis: string | null
    score: number | null
  }
  tags: string[]
  profitQuality: '正常' | '需调整' | '待确认'
  primaryExplanation: ValuationExplanation | null
  explanations: ValuationExplanation[]
}

export type CompanyValuationListPayload = {
  entries: CompanyValuationCard[]
}

export type CompanyValuationDetailPayload = {
  current: CompanyValuationCard
}

export type LoadState = 'idle' | 'loading' | 'ready' | 'error'

export type PeriodType = 1 | 3 | 5 | 'all'

export interface PeriodStats {
  period: PeriodType
  label: string
  avgPe: number | null
  minPe: number | null
  maxPe: number | null
  count: number
}
