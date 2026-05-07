export type ValuationExplanationType = 'price' | 'profit' | 'valuation' | 'business'
export type ValuationImpactDirection = 'positive' | 'neutral' | 'negative'

export type CompanyValuationExplanationInput = {
  explanationType: ValuationExplanationType | string
  title: string
  body: string
  impactDirection?: ValuationImpactDirection | string | null
  isRecurring?: boolean | null
  confidence?: number | null
}

export type CompanyValuationCardInput = {
  company: {
    id: string
    symbol: string
    market: string
    name: string
    currency?: string | null
  }
  entry?: {
    entryType: string
    title?: string | null
    note?: string | null
  } | null
  latestValuation?: {
    asOfDate: Date | string
    price?: number | null
    ttmEps?: number | null
    ttmPe?: number | null
    profitLinePrice?: number | null
    referenceLinePrice?: number | null
    upsideToProfitLine?: number | null
    upsideToReferenceLine?: number | null
  } | null
  latestExploration?: {
    summary?: string | null
    thesis?: string | null
    score?: number | null
    tags?: string | null
  } | null
  explanations?: readonly CompanyValuationExplanationInput[]
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
  primaryExplanation: CompanyValuationExplanationInput | null
  explanations: CompanyValuationExplanationInput[]
}

export function parseJsonArray(value: string | null | undefined): string[] {
  if (!value) return []

  try {
    const parsed = JSON.parse(value)
    if (!Array.isArray(parsed)) return []
    return parsed.filter((item): item is string => typeof item === 'string')
  } catch {
    return []
  }
}

export function pickPrimaryExplanation(
  explanations: readonly CompanyValuationExplanationInput[] = [],
) {
  return (
    explanations.find(
      (explanation) =>
        explanation.explanationType === 'profit' && explanation.isRecurring === false,
    ) ||
    explanations.find((explanation) => explanation.explanationType === 'profit') ||
    explanations.find((explanation) => explanation.explanationType === 'price') ||
    explanations[0] ||
    null
  )
}

function toDateString(value: Date | string | null | undefined) {
  if (!value) return null
  if (value instanceof Date) return value.toISOString().slice(0, 10)
  return value.slice(0, 10)
}

function profitQualityFor(
  explanations: readonly CompanyValuationExplanationInput[],
): CompanyValuationCard['profitQuality'] {
  const hasProfitExplanation = explanations.some(
    (explanation) => explanation.explanationType === 'profit',
  )
  const hasNonRecurringProfit = explanations.some(
    (explanation) =>
      explanation.explanationType === 'profit' && explanation.isRecurring === false,
  )

  if (hasNonRecurringProfit) return '需调整'
  if (hasProfitExplanation) return '正常'
  return '待确认'
}

export function buildCompanyValuationCard(
  input: CompanyValuationCardInput,
): CompanyValuationCard {
  const explanations = [...(input.explanations || [])]
  const latestValuation = input.latestValuation

  return {
    id: input.company.id,
    symbol: input.company.symbol,
    market: input.company.market,
    title: input.entry?.title || input.company.name,
    currency: input.company.currency || null,
    entryType: input.entry?.entryType || 'manual',
    entryNote: input.entry?.note || null,
    metrics: {
      asOfDate: toDateString(latestValuation?.asOfDate),
      price: latestValuation?.price ?? null,
      ttmEps: latestValuation?.ttmEps ?? null,
      ttmPe: latestValuation?.ttmPe ?? null,
      profitLinePrice: latestValuation?.profitLinePrice ?? null,
      referenceLinePrice: latestValuation?.referenceLinePrice ?? null,
      upsideToProfitLine: latestValuation?.upsideToProfitLine ?? null,
      upsideToReferenceLine: latestValuation?.upsideToReferenceLine ?? null,
    },
    exploration: {
      summary: input.latestExploration?.summary || null,
      thesis: input.latestExploration?.thesis || null,
      score: input.latestExploration?.score ?? null,
    },
    tags: parseJsonArray(input.latestExploration?.tags),
    profitQuality: profitQualityFor(explanations),
    primaryExplanation: pickPrimaryExplanation(explanations),
    explanations,
  }
}
