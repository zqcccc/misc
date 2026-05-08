import type { CompanyValuationCard } from './types'

function normalizedSymbol(value: string) {
  return value.trim().toUpperCase().replace(/\.(SH|SZ|HK|US)$/i, '')
}

function isSameCompany(a: CompanyValuationCard, b: CompanyValuationCard) {
  return (
    a.id === b.id ||
    (a.market === b.market && normalizedSymbol(a.symbol) === normalizedSymbol(b.symbol))
  )
}

function textLength(value: string | null | undefined) {
  return value?.trim().length || 0
}

function explanationScore(card: CompanyValuationCard) {
  return card.explanations.reduce((total, explanation) => {
    return total + 200 + textLength(explanation.title) + textLength(explanation.body)
  }, 0)
}

function explorationScore(card: CompanyValuationCard) {
  return (
    textLength(card.exploration.summary) +
    textLength(card.exploration.thesis) +
    card.tags.length * 20
  )
}

export function mergeCompanyValuationDetail(
  current: CompanyValuationCard | null,
  incoming: CompanyValuationCard,
): CompanyValuationCard {
  if (!current || !isSameCompany(current, incoming)) return incoming

  const merged: CompanyValuationCard = {
    ...incoming,
    entryType: current.entryType || incoming.entryType,
    entryNote: current.entryNote ?? incoming.entryNote,
  }

  if (explanationScore(current) > explanationScore(incoming)) {
    merged.explanations = current.explanations
    merged.primaryExplanation = current.primaryExplanation
    merged.profitQuality = current.profitQuality
  }

  if (explorationScore(current) > explorationScore(incoming)) {
    merged.exploration = current.exploration
    merged.tags = current.tags
  }

  return merged
}
