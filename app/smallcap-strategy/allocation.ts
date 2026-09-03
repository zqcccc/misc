export type AllocationHolding = {
  code: string
  price: number
  target_weight: number
}

export type HoldingExecution = {
  shares: number
  costYuan: number
  isKcb: boolean
  funded: boolean
}

export type PortfolioExecution = {
  byCode: Record<string, HoldingExecution>
  investedYuan: number
  remainingYuan: number
  fundedCount: number
}

type WorkingHolding = AllocationHolding & {
  index: number
  priceCents: number
  minShares: number
  stepShares: number
  minCostCents: number
  shares: number
  costCents: number
  desiredCostCents: number
  isKcb: boolean
  isFlexibleKcb: boolean
}

function isKcbCode(code: string) {
  return code.startsWith('sh688') || code.startsWith('688')
}

/**
 * 在 A 股最小委托单位约束下，对整套组合统一分配资金。
 *
 * 优先级：
 * 1. 尽量覆盖更多组合标的；
 * 2. 在可交易单位内尽量贴近目标权重；
 * 3. 将离散取整后的剩余资金继续投入，避免逐只截断造成大量闲置现金。
 */
export function allocatePortfolio(
  holdings: AllocationHolding[],
  totalCapitalYuan: number,
  roundKcbHundred = false,
): PortfolioExecution {
  const budgetCents = Math.max(0, Math.round(totalCapitalYuan * 100))
  const working: WorkingHolding[] = holdings
    .map((holding, index) => {
      const priceCents = Math.round(Number(holding.price) * 100)
      const isKcb = isKcbCode(holding.code)
      const minShares = isKcb ? 200 : 100
      const stepShares = isKcb && !roundKcbHundred ? 1 : 100

      return {
        ...holding,
        index,
        priceCents,
        minShares,
        stepShares,
        minCostCents: priceCents * minShares,
        shares: 0,
        costCents: 0,
        desiredCostCents: 0,
        isKcb,
        isFlexibleKcb: isKcb && !roundKcbHundred,
      }
    })
    .filter((holding) => holding.priceCents > 0)

  let spentCents = 0

  // 最小买入成本从低到高选择，可在给定本金下最大化实际覆盖的标的数量。
  const minimumLots = [...working].sort(
    (a, b) =>
      a.minCostCents - b.minCostCents ||
      b.target_weight - a.target_weight ||
      a.index - b.index,
  )

  for (const holding of minimumLots) {
    if (spentCents + holding.minCostCents > budgetCents) continue
    holding.shares = holding.minShares
    holding.costCents = holding.minCostCents
    spentCents += holding.minCostCents
  }

  const funded = working.filter((holding) => holding.shares > 0)
  const fundedWeight = funded.reduce(
    (sum, holding) => sum + Math.max(0, Number(holding.target_weight) || 0),
    0,
  )

  for (const holding of funded) {
    holding.desiredCostCents = fundedWeight > 0
      ? budgetCents * (Math.max(0, holding.target_weight) / fundedWeight)
      : budgetCents / Math.max(1, funded.length)
  }

  // 先给主板/创业板以及“整百股”模式下的科创板按手补仓。
  // 每次补给当前相对目标仓位最低的标的，避免资金只堆到最便宜的一只上。
  while (true) {
    const remainingCents = budgetCents - spentCents
    const candidate = funded
      .filter((holding) => {
        if (holding.isFlexibleKcb) return false
        const stepCost = holding.priceCents * holding.stepShares
        return (
          stepCost <= remainingCents &&
          holding.costCents + stepCost <= holding.desiredCostCents
        )
      })
      .sort((a, b) => {
        const ratioA = a.costCents / Math.max(1, a.desiredCostCents)
        const ratioB = b.costCents / Math.max(1, b.desiredCostCents)
        return ratioA - ratioB || a.index - b.index
      })[0]

    if (!candidate) break
    const stepCost = candidate.priceCents * candidate.stepShares
    candidate.shares += candidate.stepShares
    candidate.costCents += stepCost
    spentCents += stepCost
  }

  // 科创板达到 200 股后可逐股增加：先补到目标仓位附近。
  const flexibleKcb = funded
    .filter((holding) => holding.isFlexibleKcb)
    .sort((a, b) => {
      const ratioA = a.costCents / Math.max(1, a.desiredCostCents)
      const ratioB = b.costCents / Math.max(1, b.desiredCostCents)
      return ratioA - ratioB || a.index - b.index
    })

  for (const holding of flexibleKcb) {
    const remainingCents = budgetCents - spentCents
    const targetGapCents = Math.max(0, holding.desiredCostCents - holding.costCents)
    const additionalShares = Math.min(
      Math.floor(remainingCents / holding.priceCents),
      Math.floor(targetGapCents / holding.priceCents),
    )
    if (additionalShares <= 0) continue
    const additionalCost = additionalShares * holding.priceCents
    holding.shares += additionalShares
    holding.costCents += additionalCost
    spentCents += additionalCost
  }

  // 离散手数造成的尾差继续投入。精确股数模式优先作为“尾差吸收器”；
  // 没有可逐股增加的科创板时，再补当前相对仓位最低且买得起的一手。
  if (flexibleKcb.length > 0) {
    const filler = [...flexibleKcb]
      .filter((holding) => holding.priceCents <= budgetCents - spentCents)
      .sort((a, b) => a.priceCents - b.priceCents || a.index - b.index)[0]
    if (filler) {
      const additionalShares = Math.floor((budgetCents - spentCents) / filler.priceCents)
      const additionalCost = additionalShares * filler.priceCents
      filler.shares += additionalShares
      filler.costCents += additionalCost
      spentCents += additionalCost
    }
  } else {
    while (true) {
      const remainingCents = budgetCents - spentCents
      const candidate = funded
        .filter((holding) => holding.priceCents * holding.stepShares <= remainingCents)
        .sort((a, b) => {
          const ratioA = a.costCents / Math.max(1, a.desiredCostCents)
          const ratioB = b.costCents / Math.max(1, b.desiredCostCents)
          return ratioA - ratioB || a.index - b.index
        })[0]
      if (!candidate) break
      const stepCost = candidate.priceCents * candidate.stepShares
      candidate.shares += candidate.stepShares
      candidate.costCents += stepCost
      spentCents += stepCost
    }
  }

  const byCode: Record<string, HoldingExecution> = {}
  const workingByIndex = new Map(working.map((holding) => [holding.index, holding]))
  holdings.forEach((holding, index) => {
    const allocated = workingByIndex.get(index)
    const costCents = allocated?.costCents || 0
    byCode[holding.code] = {
      shares: allocated?.shares || 0,
      costYuan: costCents / 100,
      isKcb: isKcbCode(holding.code),
      funded: Boolean(allocated?.shares),
    }
  })

  return {
    byCode,
    investedYuan: spentCents / 100,
    remainingYuan: (budgetCents - spentCents) / 100,
    fundedCount: funded.length,
  }
}

export function formatHoldingExecution(
  code: string,
  shares: number,
  roundKcbHundred = false,
) {
  const isKcb = isKcbCode(code)
  if (shares <= 0) {
    return {
      shares: 0,
      label: '本轮未分配',
      sub: '本金不足以覆盖全部标的',
      isKcb,
    }
  }

  if (isKcb && !roundKcbHundred) {
    return {
      shares,
      label: `${shares.toLocaleString()} 股`,
      sub: '科创板·200股起购，之后逐股递增',
      isKcb,
    }
  }

  const hands = shares / 100
  return {
    shares,
    label: `${hands.toLocaleString()} 手 (${shares.toLocaleString()} 股)`,
    sub: isKcb ? '科创板·整百股委托' : '整手 (100股整数倍)',
    isKcb,
  }
}
